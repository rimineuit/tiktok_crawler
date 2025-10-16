from typing import Iterable, List, Tuple, Any
import pandas as pd
import anyio

# ---------- Cleaning ----------
def _clean_text_series(texts: pd.Series) -> pd.Series:
    s = texts.fillna('').astype(str).str.strip().str.lower()
    s = (s
         .str.replace(r'https?://\S+|www\.\S+', ' ', regex=True)
         .str.replace(r'[^\w\s]', ' ', regex=True)
         .str.replace(r'_', ' ', regex=True)
         .str.replace(r'\s+', ' ', regex=True)
         .str.strip())
    return s

# ---------- Helpers ----------
def unique_preserve_order(iterable: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in iterable:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

def build_ngrams_df(df_text: pd.DataFrame, nmin: int, nmax: int,
                    distinct: bool = True, drop_empty: bool = True) -> pd.DataFrame:
    if 'text' not in df_text.columns:
        raise ValueError("df_text phải có cột 'text'.")

    rows: List[Tuple[Any, int, List[str]]] = []
    text_series = df_text['text'].fillna('').astype(str)

    for id_, text in text_series.items():
        toks = text.split()
        L = len(toks)
        for n in range(nmin, nmax + 1):
            if L < n:
                grams_list: List[str] = []
            else:
                grams_iter = (" ".join(toks[i:i + n]) for i in range(L - n + 1))
                grams_list = unique_preserve_order(grams_iter) if distinct else list(grams_iter)
            rows.append((id_, n, grams_list))

    out = pd.DataFrame(rows, columns=['id', 'n', 'list_n_gram'])
    if drop_empty:
        out = out[out['list_n_gram'].map(bool)].reset_index(drop=True)
    return out


def compute_groups_sync(df_text: pd.DataFrame,
                        nmin: int, nmax: int, min_id_count: int) -> pd.DataFrame:
    ngrams_df = build_ngrams_df(df_text, nmin=nmin, nmax=nmax, distinct=True, drop_empty=True)

    exploded = (
        ngrams_df
        .explode('list_n_gram', ignore_index=False)
        .rename(columns={'list_n_gram': 'ngram'})
    )
    exploded = exploded[exploded['ngram'].notna() & (exploded['ngram'] != '')]
    exploded = exploded.drop_duplicates(subset=['id', 'n', 'ngram'])

    dups = (
        exploded.groupby(['n', 'ngram'])['id']
        .agg(lambda s: sorted(set(s)))
        .reset_index()
        .rename(columns={'id': 'ids'})
    )
    dups['id_count'] = dups['ids'].str.len()

    dups = dups[dups['id_count'] >= 2].sort_values(
        ['n', 'id_count'], ascending=[True, False]
    ).reset_index(drop=True)

    dups = dups.copy()
    dups['ids'] = dups['ids'].map(lambda L: sorted(set(L)))
    dups['ids_key'] = dups['ids'].map(tuple)
    dups['n_max'] = dups.groupby('ids_key')['n'].transform('max')
    dups_keep = dups[dups['n'] == dups['n_max']].drop(columns=['n_max']).copy()

    groups = (
        dups_keep
        .groupby(['ids_key', 'n'], as_index=False)
        .agg(
            ngrams=('ngram', lambda s: sorted(set(s))),
            ngram_count=('ngram', 'nunique')
        )
    )
    groups['ids'] = groups['ids_key'].map(list)
    groups['id_count'] = groups['ids'].str.len()
    groups = groups[['n', 'ids', 'id_count', 'ngram_count', 'ngrams']]

    g = groups.copy()
    g['ids'] = g['ids'].map(lambda L: sorted(set(L)))
    g['ids_set'] = g['ids'].map(frozenset)
    g_sorted = g.sort_values(['n', 'id_count', 'ngram_count'],
                             ascending=[False, False, False]).reset_index(drop=True)

    kept_idx: List[int] = []
    kept: List[Tuple[int, frozenset]] = []
    for i, row in g_sorted.iterrows():
        s = row['ids_set']
        ncur = int(row['n'])
        conflict = any(((nkept > ncur) or (nkept == ncur)) and (not s.isdisjoint(ks))
                       for nkept, ks in kept)
        if conflict:
            continue
        kept_idx.append(i)
        kept.append((ncur, s))

    groups_pruned = (
        g_sorted.loc[kept_idx]
        .drop(columns=['ids_set'])
        .sort_values(['id_count', 'n', 'ngram_count'], ascending=[False, False, False])
        .reset_index(drop=True)
    )

    groups_pruned = groups_pruned[groups_pruned['id_count'] >= min_id_count].reset_index(drop=True)
    return groups_pruned


# ---------- ASYNC ENTRYPOINT ----------
async def group_ngrams_from_lists(ids: List[Any],
                                  transcripts: List[str],
                                  nmin: int = 2,
                                  nmax: int = 5,
                                  min_id_count: int = 2) -> List[dict]:
    """
    Nhận list ids và list transcripts, làm sạch text, dựng DataFrame,
    rồi tính nhóm n-gram (chạy trong thread để không block event loop).
    Trả về list[dict] để dùng trực tiếp trong API FastAPI.
    """
    if len(ids) != len(transcripts):
        raise ValueError("ids và transcripts phải có cùng độ dài.")

    # Gộp transcript trùng id (nếu có)
    df_raw = pd.DataFrame({'id': ids, 'raw_text': transcripts})
    df_agg = (df_raw
              .groupby('id', as_index=True)['raw_text']
              .agg(lambda s: " ".join([x for x in s if isinstance(x, str)]))
              .to_frame())

    # Làm sạch + chuẩn hóa vào cột 'text'
    df_agg['text'] = _clean_text_series(df_agg['raw_text'])
    df_text = df_agg[['text']].copy()

    # Chạy tính toán trong threadpool
    df_result = await anyio.to_thread.run_sync(
        compute_groups_sync, df_text, nmin, nmax, min_id_count
    )

    # ✅ Trả về dạng list[dict] (để FastAPI trả JSON luôn)
    return df_result.to_dict(orient="records")

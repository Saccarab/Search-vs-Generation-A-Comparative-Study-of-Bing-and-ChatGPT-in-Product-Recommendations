import pandas as pd
import ast

from urllib.parse import urlparse

# Paths
BING_PATH = "../../data/Bing data/modified/bing.xlsx"
CHATGPT_PATH = "../../data/ChatGPT data/modified/chatgpt.xlsx" 


# -------------------- Data --------------------

def get_bing_df(grouped: bool = True):
    df = pd.read_excel(BING_PATH)
    df = df[[
        "query", "product", "market_type", "query_level",
        "content", "url", "domain", "recommended_products"
    ]]
    return _process_df(
        df, 
        list_columns = ["recommended_products"],
        agg_columns = ["content", "url", "domain", "recommended_products"] if grouped else None,
        grouped = grouped
    )
    
def get_chatgpt_df(grouped: bool = True):
    df = pd.read_excel(CHATGPT_PATH)
    df = df[[
        "query", "product", "market_type", "query_level",
        "response_text", "sources_cited", "sources_additional", "recommended_products"
    ]]
    return _process_df(
        df,
        list_columns = ["sources_cited", "sources_additional", "recommended_products"],
        agg_columns = ["response_text", "sources_cited", "sources_additional", "recommended_products"] if grouped else None,
        grouped = grouped
    )


# -------------------- Helper --------------------

def _process_df(df: pd.DataFrame, list_columns: list[str], agg_columns: list[str] = None, grouped:bool = True):
    for col in list_columns:
        df[col] = df[col].apply(_parse_col_to_list)
    
    if grouped and agg_columns:
        group_keys = ["query", "product", "market_type", "query_level"]
        df = df.groupby(group_keys, as_index = False, sort = False).agg(
            {col: list for col in agg_columns}
        )   
    return df

def _parse_col_to_list(string_array: str) -> list:
    if pd.isna(string_array):  
        return []    
    try:
        return ast.literal_eval(string_array)
    except:
        return []

def _extract_domain(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        return ""
    
    parsed = urlparse(url.strip())
    netloc = parsed.netloc or parsed.path

    if netloc.startswith("www."):
        netloc = netloc[4:]
    
    return netloc
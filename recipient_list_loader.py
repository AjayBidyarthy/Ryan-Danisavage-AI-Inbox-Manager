import io
import pandas as pd

from supabase_client import (
    get_user_id_by_email,
    get_user_company_file_ids,
    fetch_file_record,
    decode_file_data_hex,
    upload_master_list,
    download_master_list,
)

class RecipientListLoaderError(Exception):
    pass

def read_file_from_bytes(byte_data: bytes) -> pd.DataFrame:
    """
    Try to parse byte_data as XLSX, then XLS, then CSV.
    Raise if all formats fail.
    """
    errors = []
    # XLSX
    try:
        return pd.read_excel(io.BytesIO(byte_data), engine="openpyxl")
    except Exception as e:
        errors.append(f".xlsx: {e}")
    # XLS
    try:
        return pd.read_excel(io.BytesIO(byte_data), engine="xlrd")
    except Exception as e:
        errors.append(f".xls: {e}")
    # CSV
    try:
        return pd.read_csv(io.BytesIO(byte_data))
    except Exception as e:
        errors.append(f".csv: {e}")

    raise RecipientListLoaderError(
        "Could not parse file bytes:\n" + "\n".join(errors)
    )

def load_user_recipient_lists(user_email: str) -> dict[str, pd.DataFrame]:
    """
    Load all recipient list files selected by a user into DataFrames.
    Returns a dict mapping file_id → DataFrame.
    """
    user_id = get_user_id_by_email(user_email)
    if not user_id:
        raise RecipientListLoaderError(f"No user found for email: {user_email}")

    lists: dict[str, pd.DataFrame] = {}
    file_ids = get_user_company_file_ids(user_id)

    for fid in file_ids:
        record = fetch_file_record(fid)
        if not record:
            continue
        raw_bytes = decode_file_data_hex(record["file_data"])
        df = read_file_from_bytes(raw_bytes)
        lists[fid] = df

    return lists

def compile_and_store_master_list(user_email: str) -> None:
    """
    Fetch, decode, and combine all of a user's recipient lists,
    then upload the concatenated CSV to Supabase Storage.
    """
    lists = load_user_recipient_lists(user_email)
    if not lists:
        raise RecipientListLoaderError(f"No lists to compile for {user_email}")

    master_df = pd.concat(lists.values(), ignore_index=True)

    buffer = io.BytesIO()
    master_df.to_csv(buffer, index=False)
    csv_bytes = buffer.getvalue()

    success = upload_master_list(user_email, csv_bytes)
    if not success:
        raise RecipientListLoaderError(f"Failed to upload master list for {user_email}")
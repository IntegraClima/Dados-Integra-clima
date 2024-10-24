from pyarrow import dataset as ds
from pysus.ftp.databases.sinan import SINAN
from pysus.preprocessing.decoders import add_dv
from pysus.online_data import IBGE
from typing import List, Optional, Union
import os
import pandas as pd

def add_dv_safe(geocode):
    try:
        return add_dv(geocode)
    except Exception as e:
        print(f"Error processing geocode {geocode}: {e}")
        return 0
    
def last_day_of_year(year):
    try:
        last_day = pd.to_datetime(year + "-12-31")
        today = pd.Timestamp.today()
        if last_day > today:
            last_day = today
        return last_day
    except Exception as e:
        print(f"Error processing year {year}: {e}")
        return None

def download_data(
    dis_code,
    year: Optional[Union[str, int, list]] = None,
    data_dir: str = 'data/pysus'
) -> str:
    sinan = SINAN().load()
    files = sinan.get_files(dis_code=[dis_code], year=year)
    dataset_dir = os.path.join(data_dir, dis_code)
    parquets = sinan.download(files, local_dir=dataset_dir)
    return [parquet.path for parquet in parquets]


def transform_to_visao(
    parquet_paths: List[str],
    name: str = None,
    year_col: str = "NU_ANO",
    geocode_col: str = "ID_MUNICIP"
) -> pd.DataFrame:
    df_list = []
    pop = IBGE.get_population(year=2021)
    for parquet in parquet_paths:
        print(parquet)
        group_cols = [year_col, geocode_col]
        data_agg = (
            ds.dataset(parquet, format='parquet')
            .to_table(columns=group_cols)
            .group_by(group_cols)
            .aggregate([([], "count_all")])
            .to_pandas()
            .rename(columns={year_col: "data", geocode_col: "geocode",
                             "count_all": "valor"})
        )
        data_agg["geocode"] = data_agg["geocode"].str.strip().apply(add_dv_safe).astype(str)
        data_agg = data_agg[data_agg["geocode"].isin(pop["MUNIC_RES"].astype(str))]
        data_agg["data"] = data_agg["data"].apply(last_day_of_year)
        data_agg["data"] = pd.to_datetime(data_agg["data"])
        data_agg.dropna(inplace=True)
        df_list.append(data_agg)
    df = pd.concat(df_list, ignore_index=True).sort_values(["data", "geocode"])
    return df[['geocode', 'valor', 'data']]

def transform_geocode_to_uf(df: pd.DataFrame, geocode_col: str = "geocode"):
    df_uf = df.copy()
    df_uf[geocode_col] = df_uf[geocode_col].astype(str).str[:2]
    return df_uf

def aggregate_visao_count(df: pd.DataFrame, value_col: str = "valor"):
    group_cols = [col for col in df.columns if col != value_col]
    df_agg = df.groupby(group_cols)[value_col].sum().reset_index()
    return df_agg[['geocode', 'valor', 'data']]

def generate_visao_data(
        dis_codes: List[str] = ['DENG', 'ESQU', 'LEIV', 'MALA', 'RAIV'],
        data_dir: str = "data"
):
    csv_files = []
    for dis_code in dis_codes:
        parquets = download_data(dis_code)
        df_mun = transform_to_visao(parquets)
        df_uf = transform_geocode_to_uf(df_mun)
        df_uf = aggregate_visao_count(df_uf)
        csv_municipio = os.path.join(data_dir, f"{dis_code.lower()}-municipio.csv")
        df_mun.to_csv(csv_municipio, index=False, date_format="%d/%m/%Y")
        csv_uf = os.path.join(data_dir, f"{dis_code.lower()}-uf.csv")
        df_uf.to_csv(csv_uf, index=False, date_format="%d/%m/%Y")
        csv_files.append([csv_municipio, csv_uf])


if __name__ == "__main__":
    dis_codes = ['DENG', 'ESQU', 'LEIV', 'MALA', 'RAIV']
    csv_files = generate_visao_data(dis_codes)
    print(f"Generated files: {csv_files}")

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import pandas as pd
import regionmask
import os
import geopandas as gpd
from joblib import Parallel, delayed
import rioxarray
np.seterr(all="ignore")

"""
IMPORTANTE! O código anterior estava com problemas, não calculando corretamente
a variável em nível municipal. Corrigido em 08/nov/2023.
Neste exemplo é apresentado a geração de arquivo no formato
"geojson", "shape" ou gpkg,  da variável precipitação, acumulada
em nível municipal para o Brasil. A escala de tempo pode ser
mensal ou anual, entre outras. O valor mensal de cada município é a
média das células da grade que estão dentro do seu limite.
Shape dos municípios obtidos em em:
https://www.ibge.gov.br/geociencias/organizacao-do-territorio/malhas-territoriais/15774-malhas.html?=&t=acesso-ao-produto
Geometria dos municípios foi simplificada em: https://mapshaper.org/
Arquivos shapes utilizados para este código, em: /exemplos/shape_file/
"""

def extract_municipios_data(var_resample_extrapolado, municipios_centroid_x, municipios_centroid_y, n, mask, lon, lat):
    # print(n)
    sel_mask = mask.where(mask == n).values
    id_lon = lon[np.where(~np.all(np.isnan(sel_mask), axis=0))]
    if len(id_lon) >= 1:
        id_lat = lat[np.where(~np.all(np.isnan(sel_mask), axis=1))]
        out_sel = var_resample_extrapolado.sel(latitude=slice(id_lat[0], id_lat[-1]),
                                               longitude=slice(id_lon[0], id_lon[-1])).compute().where(mask == n)

        municipios_data_pandas = np.nanmean(out_sel.values, axis=(1, 2))

    else:
        lon_municipios, lat_municipios = municipios_centroid_x[n], municipios_centroid_y[n]
        out_sel = var_resample_extrapolado.sel(latitude=lat_municipios,
                                               longitude=lon_municipios,
                                               method='nearest')
        municipios_data_pandas = out_sel.values

    return municipios_data_pandas

def etl_clima_municipios(vars=['pr', 'Tmax', 'Tmin', 'Rs', 'RH', 'u2'], time_scale="Y",
                         min_date='1961-01-31', max_date='2024-03-31'):
    # pegando o arquivo shape dos municipios
    path = os.path.join(os.getcwd(), 'data/brdwgd/shape_file/BR_Municipios_2021.shp')
    print("Carregando shapefile")
    municipios = gpd.read_file(path, encoding="utf-8")
    
    if not isinstance(vars, list):
        vars = [vars]
    
    # escolhendo a variavel, neste caso precipitação ('Tmax', 'Tmin', 'Rs', 'RH', 'u2', 'pr')
    df_complete = None
    for nvar2get in vars:
        #nvar2get = 'pr'

        # escala para amostragem "M" para mensal e "Y" para anual
        #time_scale = "ME"

        # Nome e tipo de arquivo para exportar os dados municipais, exemplo:
        # para formato shapefile: 'preci_muni_mensal.shp' ou gpkg: 'preci_muni_mensal.gpkg'
        #name2save = 'preci_muni_mensal.shp'

        # caminho dos arquivos NetCDF da grade BR-DWGD
        path_netcdf = 'data/brdwgd/netcdf_files/'

        print(f"Carregando dados netcdf para variável {nvar2get}")
        var = xr.open_mfdataset(path_netcdf + nvar2get + '*.nc')[nvar2get]

        # centróides dos municípios para serem utilizados quando
        # o município é muito pequeno e não há célula da grade dentro.
        # Vai pegar da célula mais próxima ao centroide do município
        municipios_centroid_x = municipios.to_crs(epsg=5641).centroid.to_crs(municipios.crs).x.values
        municipios_centroid_y = municipios.to_crs(epsg=5641).centroid.to_crs(municipios.crs).y.values

        # mascara dos municípios
        municipios_mask_poly = regionmask.Regions(name="municipios_mask",
                                                numbers=list(range(len(municipios))),
                                                names=list(municipios.CD_MUN),
                                                abbrevs=list(municipios.NM_MUN),
                                                outlines=list(municipios.geometry.values[i] for i in range(len(municipios))))

        # mascara continente/mar
        mask_ocean = 2 * np.ones(var.shape[1:]) * np.isnan(var.isel(time=0))
        mask_land = 1 * np.ones(var.shape[1:]) * ~np.isnan(var.isel(time=0))
        mask_array = (mask_ocean + mask_land).values

        var.coords['mask'] = xr.DataArray(mask_array, dims=('latitude', 'longitude'))

        # reamostrando para mensal. Para acumulado e média do período, use,
        # respectivamente, sum('time') e mean('time')
        #var_resample = var.resample(time=time_scale).sum('time').where(var.mask == 1).compute()
        var_resample = var.resample(time=time_scale).mean('time').where(var.mask == 1).compute() # para média

        # Extrapolando os dados gradeados, para que municípios que estão
        # no limite do Brasil tenham dados.
        print("Extrapolando")
        var_resample.rio.write_nodata(np.nan, inplace=True)
        var_resample.rio.write_crs("epsg:4326", inplace=True)
        var_resample_extrapolado = var_resample.rio.interpolate_na()

        mask_munic = municipios_mask_poly.mask(var_resample_extrapolado['longitude'],
                                            var_resample_extrapolado['latitude'])

        municipios_data_pandas = np.empty((len(var_resample_extrapolado.time)))
        lat = mask_munic.latitude.values
        lon = mask_munic.longitude.values

        # start = time.time()
        # c = coletando_dados(0, mask_munic, lon, lat)
        # print(time.time() - start)

        print("Extraindo dados dos municípios")
        saida = Parallel(n_jobs=-1, verbose=4, timeout=36000)(delayed(extract_municipios_data)(var_resample_extrapolado,
                                                                                municipios_centroid_x,
                                                                                municipios_centroid_y,
                                                                                n, mask_munic, lon, lat)
                                            for n in range(len(municipios.CD_MUN)))

        municipios_data = pd.DataFrame(np.empty((len(municipios.CD_MUN),
                                                len(var_resample_extrapolado.time)), dtype="float"),
                                    columns=var_resample_extrapolado.time.dt.strftime('%Y-%m-%d'),
                                    index=municipios.index)

        for n in range(len(municipios.CD_MUN)):
           municipios_data.iloc[n, :] = saida[n].astype("float")

        # concatenado dados shape com dados da grade reamostrados
        municipios_data.set_index(municipios.index)
        municipios_data = pd.concat((municipios, municipios_data), axis=1)

        # gravando
        print("Gravando")
        #municipios.to_file(name2save)

        #gdf = gpd.read_file(name2save)
        df = municipios_data.drop(columns="geometry")
        #df["VARIAVEL"] = nvar2get
        #csv_raw = f'data/brdwgd/raw_muni_mensal_{nvar2get}.csv'
        #df.to_csv(csv_raw, index=False, encoding="utf-8")

        # colunas_fixas = ['CD_MUN', 'NM_MUN', 'CD_RGI', 'NM_RGI', 'CD_RGINT', 'NM_RGINT', 
        #                  'CD_UF', 'NM_UF', 'CD_REGIAO', 'NM_REGIAO', 'CD_CONCURB', 
        #                  'NM_CONCURB', 'AREA_KM2']

        #colunas_fixas = ['CD_MUN', 'NM_MUN', 'SIGLA', 'AREA_KM2', 'VARIAVEL']
        #colunas_fixas = ['CD_MUN']
        colunas_fixas = ['CD_MUN', 'NM_MUN', 'SIGLA', 'AREA_KM2']

        colunas_validas = []

        for col in df.columns:
            try:
                data_coluna = pd.to_datetime(col, format='%Y-%m-%d')
                if min_date <= col <= max_date:  # Intervalo desejado
                    colunas_validas.append(col)
            except Exception:
                continue  # Ignora colunas que não são datas

        # Transpoe
        df_transformado = df.melt(id_vars=colunas_fixas, 
                                value_vars=colunas_validas, 
                                var_name='DATA', 
                                value_name=nvar2get)

        print(df_transformado)
        if df_complete is None:
            df_complete = df_transformado
        else:
            df_complete = pd.merge(df_complete, df_transformado, on=colunas_fixas.append("data"), how="outer")

    csv_final = f'data/brdwgd/dados_clima_municipio_{time_scale.lower()}.csv'
    
    #df_complete = pd.merge(municipios, df_complete, on="CD_MUN", how="outer")
    #df_complete.columns = df_complete.columns.str.lower()
    df_complete = df_complete.sort_values(by=["data", "CD_MUN"], ascending=[False, True])
    df_complete.to_csv(csv_final, index=False, encoding='utf-8')

    print(f"Arquivo {csv_final} salvo com sucesso!")
    return df_complete

def transform_to_visao(df, data_dir, vars=['pr', 'Tmax', 'Tmin', 'Rs', 'RH', 'u2']):
    # Transforma a coluna de data para o formato desejado
    res = pd.DataFrame({
        "geocode": df['CD_MUN'],
        "data": pd.to_datetime(df['DATA'], format='%Y-%m-%d').dt.strftime('%d/%m/%Y'),
        "area": df['AREA_KM2']
    })
    for variavel in vars:
        # Salva o dataframe em um arquivo CSV
        var_name = variavel.lower()
        csv_file = os.path.join(data_dir, f"clima-{var_name}-municipio.csv")
        res["valor"] = df[variavel].round(0).astype(int)
        res[["geocode", "valor", "data"]].to_csv(csv_file, index=False)
        
        # Agrupa os dados por UF e salva em outro arquivo CSV
        csv_uf_file = os.path.join(data_dir, f"clima-{var_name}-uf.csv")
        res_uf = res.copy()
        res_uf["geocode"] = res_uf["geocode"].astype(str).str[:2]
        res_uf = res_uf.groupby(['data', 'geocode']).apply(
            lambda x: np.average(x["valor"], weights=x["area"]).round(0).astype(int)
        ).reset_index(name="valor")
        print(var_name)
        print(csv_uf_file)
        res_uf[["geocode", "valor", "data"]].to_csv(csv_uf_file, index=False)

df = etl_clima_municipios(time_scale='YE', min_date='2000-01-01')
#df = pd.read_csv('data/brdwgd/dados_clima_municipio_ye.csv')
transform_to_visao(df, 'data/visao/')
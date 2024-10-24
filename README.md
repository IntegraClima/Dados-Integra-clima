# IntegraClima - Dados

Repositório com a extração e tratamento de dados de interesse do projeto Integra Clima.
Os dados são extraídos de sistemas como o SINAN do DATASUS e transformados para CSV no formato do [Visão](https://visao.ibict.br/).

## 1 Configuração do ambiente

Você precisa ter o `python` instalado na máquina para executar o código, de preferência na versão 3.11 ou acima.

Primeiro, crie um ambiente virtual Python, executando em um terminal, no diretório raíz do projeto:

```bash
python -m venv .venv
```

Em seguida, ative o ambiente virtual com o comando apropriado para o seu sistema operacional:

- **Linux/MacOS:**

    ```bash
    source .venv/bin/activate
    ```

- **Windows:**

    ```bash
    .\.venv\Scripts\activate
    ```

Com o ambiente virtual ativado, instale as dependências listadas no arquivo `requirements.txt`:

```bash
pip install -r requirements.txt
```

## 2 Dados de doenças do SINAN

São extraídos do SINAN/DATASUS dados das doenças de interesse do projeto: Dengue, Esquistossomose, Leishmaniose Tegumentar, Malária e Raiva.
Os dados são tratados e transformados no formato do Visão, contabilizando o total anual de casos confirmados por estado e município.

Para gerar os dados, após configuração do ambiente, você pode executar o comando:

```bash
python -m integradados.sinan
```

Esse comando demora bastante para executar, tendo em vista que os dados de todos os casos confirmados de cada doença precisam ser baixados do SINAN.

O script usa a biblioteca `pysus` para extração dos dados. Os dados brutos serão baixados para o diretório `data/pysus`.
Os dados transformados para o formato Visão serão salvos no diretório `data/`,
com dois arquivos por doença: `{cod_doenca}-uf.csv` e `{cod_doenca}-municipios.csv`, sendo o primeiro agregado por UF e o segundo por município.
O `cod_doenca` se refere ao código da doença no sistema SINAN.

Os arquivos gerados no diretório `data/` após rodar o script são:

- `deng-uf.csv` e `deng-municipio.csv`: casos anuais de Dengue por UF e município
- `esqu-uf.csv` e `esqu-municipio.csv`: casos anuais de Esquistossomose por UF e município
- `leiv-uf.csv` e `leiv-municipio.csv`: casos anuais de Leishmaniose Tegumentar por UF e município
- `mala-uf.csv` e `mala-municipio.csv`: casos anuais de Malária por UF e município
- `raiv-uf.csv` e `raiv-municipio.csv`: casos anuais de Raiva por UF e município

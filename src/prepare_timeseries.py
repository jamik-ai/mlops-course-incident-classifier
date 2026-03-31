import pandas as pd
from pathlib import Path

def main():
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    input_file = project_root / "data" / "processed" / "incidents_clean.csv"
    output_file = project_root / "data" / "processed" / "hourly_data.csv"

    df = pd.read_csv(input_file, sep=';')
    df['dtcreate'] = pd.to_datetime(df['dtcreate'])

    df_hourly = df.groupby(pd.Grouper(key='dtcreate', freq='H')).size().reset_index(name='count')
    df_hourly.set_index('dtcreate', inplace=True)

    df_hourly['hour'] = df_hourly.index.hour
    df_hourly['day_of_week'] = df_hourly.index.dayofweek
    df_hourly['month'] = df_hourly.index.month
    df_hourly['day_of_year'] = df_hourly.index.dayofyear
    df_hourly['is_weekend'] = (df_hourly['day_of_week'] >= 5).astype(int)

    df_hourly.dropna(subset=['count'], inplace=True)
    df_hourly.to_csv(output_file)
    print(f"Почасовые данные сохранены в {output_file} (без лагов)")

if __name__ == "__main__":
    main()
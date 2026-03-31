import pandas as pd
from pathlib import Path

def main():
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    input_file = project_root / "data" / "processed" / "incidents_clean.csv"
    output_file = project_root / "data" / "processed" / "hourly_data.csv"

    df = pd.read_csv(input_file, sep=';')
    df['dtcreate'] = pd.to_datetime(df['dtcreate'])

    # Агрегация по часам
    df_hourly = df.groupby(pd.Grouper(key='dtcreate', freq='H')).size().reset_index(name='count')
    df_hourly.set_index('dtcreate', inplace=True)

    # Временные признаки
    df_hourly['hour'] = df_hourly.index.hour
    df_hourly['day_of_week'] = df_hourly.index.dayofweek
    df_hourly['month'] = df_hourly.index.month
    df_hourly['day_of_year'] = df_hourly.index.dayofyear
    df_hourly['is_weekend'] = (df_hourly['day_of_week'] >= 5).astype(int)

    # Лаговые признаки
    for lag in [1, 2, 3, 24, 48, 168]:
        df_hourly[f'lag_{lag}'] = df_hourly['count'].shift(lag)

    # Скользящие средние
    df_hourly['rolling_mean_24'] = df_hourly['count'].rolling(24).mean()
    df_hourly['rolling_std_24'] = df_hourly['count'].rolling(24).std()

    # Удаляем строки с NaN
    df_hourly.dropna(inplace=True)

    df_hourly.to_csv(output_file)
    print(f"Почасовые данные сохранены в {output_file}")

if __name__ == "__main__":
    main()
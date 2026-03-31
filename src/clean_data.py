import pandas as pd
from pathlib import Path

# Получаем папку, в которой находится скрипт
SCRIPT_DIR = Path(__file__).parent
# Корень проекта – на уровень выше (src -> корень)
PROJECT_ROOT = SCRIPT_DIR.parent

input_file = PROJECT_ROOT / "data" / "raw" / "incidents.csv"
output_file = PROJECT_ROOT / "data" / "processed" / "incidents_clean.csv"

# Теперь можно читать
df = pd.read_csv(input_file, sep=';')

# Читаем исходный CSV
df = pd.read_csv(input_file, sep=';')

# Оставляем только нужные столбцы
df = df[['dtcreate', 'calltype_name', 'incident_type_name', 'Kp']]

# Удаляем строки с пропусками (NaN)
df = df.dropna()

# Удаляем дубликаты (полные копии строк)
df = df.drop_duplicates()

# Удаляем строки, где Kp == 0 (если нужно)
df = df[df['Kp'] != 0]

# Сохраняем результат
df.to_csv(output_file, sep=';', index=False)

print(f"Данные очищены. Сохранено {len(df)} строк.")
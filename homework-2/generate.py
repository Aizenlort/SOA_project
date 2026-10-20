import subprocess
import sys
from pathlib import Path

def run_command(command: list[str]):
    print(f"Выполняю: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Ошибка:\n{result.stderr}")
        sys.exit(1)
    if result.stdout:
        print(result.stdout)

def main():
    project_root = Path(__file__).parent
    openapi_file = project_root / "openapi.yaml"
    output_file = project_root / "src" / "api" / "models.py"

    output_file.parent.mkdir(parents=True, exist_ok=True)

    init_file = output_file.parent / "__init__.py"
    init_file.touch(exist_ok=True)

    print("--- Генерация Pydantic V2 моделей из OpenAPI ---")
    run_command([
        "datamodel-codegen",
        "--input", str(openapi_file),
        "--input-file-type", "openapi",
        "--output", str(output_file),
        "--output-model-type", "pydantic_v2.BaseModel",
        "--use-schema-description",
        "--use-field-description",
        "--use-standard-collections",
        "--use-union-operator",
        "--use-title-as-name",
        "--allow-population-by-field-name",
        "--disable-timestamp"
    ])

    print(f"Модели сгенерированы в {output_file}")

if __name__ == "__main__":
    main()
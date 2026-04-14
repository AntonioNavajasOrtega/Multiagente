import subprocess
import os
import sys

# Definición de configuraciones y sus etiquetas descriptivas
configs = [
    ("../config/small_simple.json", "small_simple"),
    ("../config/large_sparse.json", "large_sparse"),
    ("../config/congested.json", "congested"),
]

# Modos de simulación disponibles en main.py
modes = ["simple", "coordinated", "rl"]

def run_experiment(scenario_path, scenario_label, mode):
    """Ejecuta una simulación individual."""
    output_file = f"../results/res_{scenario_label}_{mode}.json"
    print(f"\n{'='*60}")
    print(f" EJECUTANDO: Escenario={scenario_label}, Modo={mode}")
    print(f"{'='*60}")
    
    cmd = [
        sys.executable, "../main.py", "simulate",
        "--scenario", scenario_path,
        "--mode", mode,
        "--output", output_file
    ]
    
    # Para el modo RL, limitamos episodios para que la ejecución sea ágil en esta prueba
    if mode == "rl":
        cmd += ["--episodes", "20"]
        print("  (RL: Usando 20 episodios de entrenamiento)")

    try:
        # Ejecutamos el comando
        subprocess.run(cmd, check=True)
        print(f"\n[OK] Resultado guardado en: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Falló la ejecución de {scenario_label} en modo {mode}")
        print(f"Detalles: {e}")

def main():
    # Asegurar que el directorio de resultados existe
    if not os.path.exists("../results"):
        os.makedirs("../results")
        print("[Info] Directorio 'results/' creado.")

    # Ejecutar todas las combinaciones
    for path, label in configs:
        if not os.path.exists(path):
            print(f"[Aviso] No se encontró el archivo: {path}. Saltando...")
            continue
            
        for mode in modes:
            run_experiment(path, label, mode)

    print(f"\n{'='*60}")
    print(" PROCESO COMPLETADO: Todas las simulaciones han finalizado.")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()

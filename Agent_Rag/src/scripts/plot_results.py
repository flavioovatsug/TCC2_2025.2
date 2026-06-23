import os
import json
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd

def load_data(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def aggregate_data(data):
    df = pd.DataFrame(data['results'])
    
    # Calculate average time per scenario
    time_agg = df.groupby('scenario')['time_total_s'].mean().reset_index()
    
    # Calculate average relationships (Total vs LLM)
    rels_agg = df.groupby('scenario')[['total_relationships', 'llm_relationships']].mean().reset_index()
    
    # Calculate average types of relationships
    df['num_llm_types'] = df['llm_rel_types'].apply(len)
    types_agg = df.groupby('scenario')['num_llm_types'].mean().reset_index()
    
    # Calculate average density
    density_agg = df.groupby('scenario')['graph_density'].mean().reset_index()
    
    return time_agg, rels_agg, types_agg, density_agg

def set_style():
    sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)
    plt.rcParams['font.family'] = 'sans-serif'
    
def get_scenario_names(scenarios):
    names = []
    for s in scenarios:
        if s == 'A':
            names.append('Cenário A\n(Baseline)')
        elif s == 'B':
            names.append('Cenário B\n(Prompt Cru)')
        elif s == 'C':
            names.append('Cenário C\n(Otimizado)')
        else:
            names.append(s)
    return names

def plot_time(time_agg, out_dir):
    plt.figure(figsize=(8, 6))
    scenarios = get_scenario_names(time_agg['scenario'])
    ax = sns.barplot(x=scenarios, y=time_agg['time_total_s'], palette="Blues_d")
    
    plt.title('Tempo Médio de Execução por Cenário', pad=20, fontsize=14, fontweight='bold')
    plt.ylabel('Tempo (segundos)')
    plt.xlabel('Cenário')
    
    for i, v in enumerate(time_agg['time_total_s']):
        ax.text(i, v + 0.5, f'{v:.2f}s', ha='center', va='bottom', fontweight='bold')
        
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'tempo_execucao.png'), dpi=300)
    plt.close()

def plot_relationships(rels_agg, out_dir):
    plt.figure(figsize=(9, 6))
    scenarios = get_scenario_names(rels_agg['scenario'])
    
    x = np.arange(len(scenarios))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(9, 6))
    rects1 = ax.bar(x - width/2, rels_agg['total_relationships'], width, label='Total de Relacionamentos', color='#3498db')
    rects2 = ax.bar(x + width/2, rels_agg['llm_relationships'], width, label='Relacionamentos Inferidos (IA)', color='#e74c3c')
    
    ax.set_ylabel('Quantidade (Média)')
    ax.set_title('Conexões Geradas: Totais vs Inferência Semântica', pad=20, fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(scenarios)
    ax.legend()
    
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            if height > 0 or rects == rects1:
                ax.annotate(f'{height:.1f}',
                            xy=(rect.get_x() + rect.get_width() / 2, height),
                            xytext=(0, 3),  
                            textcoords="offset points",
                            ha='center', va='bottom', fontweight='bold')

    autolabel(rects1)
    autolabel(rects2)
    
    fig.tight_layout()
    plt.savefig(os.path.join(out_dir, 'relacionamentos_comparacao.png'), dpi=300)
    plt.close()

def plot_relationship_types(types_agg, out_dir):
    plt.figure(figsize=(8, 6))
    scenarios = get_scenario_names(types_agg['scenario'])
    ax = sns.barplot(x=scenarios, y=types_agg['num_llm_types'], palette="viridis")
    
    plt.title('Diversidade Semântica (Tipos de Relacionamento IA)', pad=20, fontsize=14, fontweight='bold')
    plt.ylabel('Quantidade de Tipos Distintos')
    plt.xlabel('Cenário')
    
    for i, v in enumerate(types_agg['num_llm_types']):
        ax.text(i, v + 0.1, f'{v:.1f}', ha='center', va='bottom', fontweight='bold')
        
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'diversidade_tipos.png'), dpi=300)
    plt.close()

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    json_path = os.path.join(base_dir, 'results', 'tarefas_final.json')
    out_dir = os.path.join(base_dir, 'results', 'plots')
    
    os.makedirs(out_dir, exist_ok=True)
    
    print(f"Reading data from {json_path}...")
    data = load_data(json_path)
    
    time_agg, rels_agg, types_agg, density_agg = aggregate_data(data)
    
    set_style()
    print("Generating plots...")
    plot_time(time_agg, out_dir)
    plot_relationships(rels_agg, out_dir)
    plot_relationship_types(types_agg, out_dir)
    print(f"Plots saved successfully in {out_dir}!")

if __name__ == "__main__":
    main()

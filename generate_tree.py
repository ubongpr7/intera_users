import os

def generate_tree(path, indent=''):
    ignore = {'__pycache__', '.git', 'venv', 'migrations'}
    items = os.listdir(path)
    for item in items:
        if item in ignore:
            continue
        full_path = os.path.join(path, item)
        if os.path.isdir(full_path):
            print(f"{indent}📁 {item}")
            generate_tree(full_path, indent + '    ')
        else:
            print(f"{indent}📄 {item}")

generate_tree(os.getcwd())
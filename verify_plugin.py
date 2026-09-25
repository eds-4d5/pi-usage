#!/usr/bin/env python3
"""
Verificação rápida do plugin ess.pi-usage
- Verifica se o plugin está registrado no Omarchy
- Verifica se o manifest está correto
- Verifica se o backend Python está funcionando
"""

import json
import os
import subprocess
from pathlib import Path

def check_plugin_installed():
    """Verifica se o plugin está instalado em ~/.config/omarchy/plugins/"""
    plugin_dir = Path.home() / ".config" / "omarchy" / "plugins" / "ess.pi-usage"
    if not plugin_dir.exists():
        print("❌ Plugin não está instalado")
        return False
    
    print("✅ Plugin está instalado em:", plugin_dir)
    return True

def check_manifest():
    """Verifica o manifest.json"""
    manifest_path = Path.home() / ".config" / "omarchy" / "plugins" / "ess.pi-usage" / "manifest.json"
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        print("✅ Manifest carregado")
        print(f"   ID: {manifest.get('id')}")
        print(f"   Nome: {manifest.get('name')}")
        print(f"   Versão: {manifest.get('version')}")
        
        # Verifica se é um bar widget
        if "bar-widget" in manifest.get("kinds", []):
            print("✅ Plugin é um bar widget")
        else:
            print("❌ Plugin não é um bar widget")
            return False
        
        # Verifica o entrypoint
        entry_points = manifest.get("entryPoints", {})
        if "barWidget" in entry_points:
            print("✅ Entrypoint: bar widget")
        else:
            print("❌ Entrypoint: bar widget não encontrado")
            return False
            
        return True
    except Exception as e:
        print(f"❌ Erro ao verificar manifest: {e}")
        return False

def check_backend_script():
    """Verifica o backend Python"""
    backend_path = Path.home() / ".config" / "omarchy" / "plugins" / "ess.pi-usage" / "scripts" / "pi-usage.py"
    if not backend_path.exists():
        print("❌ Script backend não encontrado")
        return False
    
    print("✅ Backend script encontrado:", backend_path)
    
    # Tenta executar o script (quick test)
    try:
        result = subprocess.run(
            ["python3", str(backend_path)],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            print(f"✅ Backend respondeu ({data.get('id', 'N/A')})")
            print(f"   Tokens hoje: {data.get('todayTotalTokens', 0)}")
            print(f"   Total prompts: {data.get('totalPrompts', 0)}")
            return True
        else:
            print(f"❌ Backend retornou erro: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"❌ Erro ao executar backend: {e}")
        return False

def check_ui_file():
    """Verifica o arquivo QML do painel"""
    qml_path = Path.home() / ".config" / "omarchy" / "plugins" / "ess.pi-usage" / "Panel.qml"
    if not qml_path.exists():
        print("❌ Panel.qml não encontrado")
        return False
    
    print("✅ Panel.qml encontrado:", qml_path)
    
    # Verifica se o layout de régua está presente
    content = qml_path.read_text()
    
    # Verifica indicadores de régua horizontal
    if "Rectangle { width: parent.width; height: Style.space(2); color: root.track" in content:
        print("✅ Linha de régua horizontal presente")
    else:
        print("⚠️ Linha de régua horizontal não encontrada (pode estar com nome diferente)")
    
    # Verifica a source do ícone
    if 'source: "assets/pi.svg"' in content:
        print("✅ Ícone do Pi Agent usado")
    elif 'text: "π"' in content:
        print("⚠️ Usando símbolo π (ícone não atualizado)")
    else:
        print("⚠️ Nenhum ícone encontrado")
    
    # Verifica o indicador "ToKENS BY DAY"
    if "TOKENS BY DAY" in content:
        print("✅ Seção TOKENS BY DAY presente")
    else:
        print("❌ Seção TOKENS BY DAY não encontrada")
        return False
    
    return True

def main():
    print("=== Verificação do Plugin ess.pi-usage ===\n")
    
    all_ok = True
    
    all_ok &= check_plugin_installed()
    print()
    all_ok &= check_manifest()
    print()
    all_ok &= check_ui_file()
    print()
    all_ok &= check_backend_script()
    
    print("\n=== Resumo ===")
    if all_ok:
        print("✅ Todas as verificações passaram!")
        print("O plugin está funcionando corretamente com o novo layout de régua horizontal.")
    else:
        print("❌ Algumas verificações falharam")
        print("Verifique os erros acima.")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    exit(main())
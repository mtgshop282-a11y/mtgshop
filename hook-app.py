from PyInstaller.utils.hooks import collect_data_files

# Inclure les fichiers statiques et les templates
datas = collect_data_files('app', include_py_files=True)
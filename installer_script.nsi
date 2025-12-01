; Définir le nom de l'installateur
Name "MKM Gestion 1.0.0"
OutFile "MKM_GESTION1.exe"

; Définir le répertoire d'installation par défaut
InstallDir "$PROGRAMFILES\MKM_GESTION"

; Section d'installation
Section "Install"

  ; Définir le répertoire de destination
  SetOutPath "$INSTDIR"

  ; Ajouter l'exécutable
  File "dist\MKM_GESTION1.exe"

  ; Ajouter des fichiers supplémentaires (icône, licence, etc.)
  File "assets\icon.ico"

  ; Créer un raccourci sur le bureau
  CreateShortcut "$DESKTOP\MKM_GESTION.lnk" "$INSTDIR\MKM_GESTION1.exe"

  ; Créer un raccourci dans le menu Démarrer
  CreateDirectory "$SMPROGRAMS\MKM_GESTION"
  CreateShortcut "$SMPROGRAMS\MKM_GESTION\MKM_GESTION.lnk" "$INSTDIR\MKM_GESTIONS1.exe"
  CreateShortcut "$SMPROGRAMS\MKM_GESTION\Uninstall.lnk" "$INSTDIR\uninstall.exe"

  ; Enregistrer l'application pour la désinstallation
  WriteUninstaller "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MKM_GESTION" "DisplayName" "MKM GESTION"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MKM_GESTION" "UninstallString" "$INSTDIR\uninstall.exe"

SectionEnd

; Section de désinstallation
Section "Uninstall"

  ; Supprimer les fichiers installés
  Delete "$INSTDIR\MKM_GESTION1.exe"
  Delete "$INSTDIR\icon.ico"
  Delete "$INSTDIR\license.txt"
  Delete "$INSTDIR\uninstall.exe"

  ; Supprimer les raccourcis
  Delete "$DESKTOP\MKM_GESTION.lnk"
  Delete "$SMPROGRAMS\MKM_GESTION\MKM_GESTION.lnk"
  Delete "$SMPROGRAMS\MKM_GESTION\Uninstall.lnk"
  RMDir "$SMPROGRAMS\MKM_GESTION"

  ; Supprimer le répertoire d'installation
  RMDir "$INSTDIR"

  ; Supprimer l'entrée de registre
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MKM_GESTION"

SectionEnd
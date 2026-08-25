# Smart Finance Platform Windows 安装包（NSIS）
# 由 CI 在 windows-latest 上调用预装的 makensis 构建（在 flutter_client 目录下执行）：
#   makensis /DVERSION=1.6.0 /DSRCDIR="$PWD\build\windows\x64\runner\Release" windows/packaging/installer.nsi
#
# 路径语义：makensis 编译期相对路径以「本脚本所在目录」为基准，且部分平台对带 ..
# 段的递归通配解析不稳，故源目录由调用方以绝对路径 /DSRCDIR 注入。
# 本地无签名证书，安装包与便携 zip 同等接受 SmartScreen 提示。
Unicode true
RequestExecutionLevel admin

!define APPNAME "Smart Finance Platform"
!define DISPLAYNAME "智慧金融分析平台"
!define REGKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\SmartFinancePlatform"
!ifndef VERSION
  !define VERSION "0.0.0-dev"
!endif
!ifndef SRCDIR
  !error "缺少 /DSRCDIR=<绝对路径>（指向 build/windows/x64/runner/Release）"
!endif

Name "${APPNAME} ${VERSION}"
InstallDir "$PROGRAMFILES64\${APPNAME}"
OutFile "../../../sff-windows-setup.exe"

Page directory
Page instfiles

Section "install"
  SetOutPath "$INSTDIR"
  ; 绝对路径须用反斜杠；仅 * 在 NSIS 编译期通配下会匹配不到文件
  File /r "${SRCDIR}\*.*"

  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortCut "$SMPROGRAMS\${APPNAME}\${DISPLAYNAME}.lnk" "$INSTDIR\flutter_client.exe"
  CreateShortCut "$DESKTOP\${DISPLAYNAME}.lnk" "$INSTDIR\flutter_client.exe"

  WriteUninstaller "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "${REGKEY}" "DisplayName" "${DISPLAYNAME}"
  WriteRegStr HKLM "${REGKEY}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "${REGKEY}" "DisplayIcon" '"$INSTDIR\flutter_client.exe"'
  WriteRegDWORD HKLM "${REGKEY}" "NoModify" 1
  WriteRegDWORD HKLM "${REGKEY}" "NoRepair" 1
SectionEnd

Section "uninstall"
  RMDir /r "$INSTDIR"
  Delete "$SMPROGRAMS\${APPNAME}\${DISPLAYNAME}.lnk"
  Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
  RMDir "$SMPROGRAMS\${APPNAME}"
  Delete "$DESKTOP\${DISPLAYNAME}.lnk"
  Delete "$DESKTOP\${APPNAME}.lnk"
  DeleteRegKey HKLM "${REGKEY}"
SectionEnd

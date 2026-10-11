# App icon

An angular bronze R inside a browser gateway connects two nodes, reflecting OpenRagnar's role between agent clients and BrowserOS Neo. Slate and bronze match the app's existing appearance. The R matches the sidebar's subtle runic geometry; the name comes from Ragnar Lothbrok.

`AppIcon.icns` includes native 16–1024 pixel representations with a transparent margin. `AppIcon.png` is the 1024 pixel preview. Both are original project artwork generated with AppKit/Core Graphics and covered by the repository license.

To edit and regenerate on macOS, change `script/generate_icon.swift`, then run from the repository root:

```sh
swift script/generate_icon.swift
```

Staging copies the committed ICNS file into the signed bundle and declares `CFBundleIconFile`. GitHub DMG builds use the same artwork without a separate asset download or generator dependency.

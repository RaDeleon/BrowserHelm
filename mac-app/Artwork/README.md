# BrowserHelm app icon

The selected Packet Studio icon is a cyan browser frame with a routed three-node data path and arrow on graphite/navy. It contains no lettering or Viking imagery.

`BrowserHelm-master.png` is the approved image-generation concept. `AppIcon.png` is the 1024 pixel preview; `AppIcon.icns` includes native 16–1024 pixel representations with transparent margins. The sidebar and packaged app use this same artwork.

Regenerate native sizes on macOS with `swift script/generate_icon.swift`. Staging copies both AppIcon files into the signed bundle. CI uses the committed artwork with no network asset dependency.

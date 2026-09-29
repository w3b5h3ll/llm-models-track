# Web fonts

This site hosts its fonts locally. No external font service is contacted.

| Use | Typeface | Source |
| --- | --- | --- |
| Latin / English / table numbers | Inter Variable 4.001 (git-9221beed3) | https://github.com/rsms/inter — `docs/font-files/InterVariable.woff2` |
| Simplified Chinese | Source Han Sans SC 2.005, Regular / Bold | Adobe Source Han Sans; extracted from the installed official 2.005 font collection |
| Model IDs / code | JetBrains Mono Regular | https://github.com/JetBrains/JetBrainsMono |

The matching SIL Open Font License files are included in this directory.

Inter and JetBrains Mono are upstream WOFF2 files, unchanged. Source Han Sans was converted to WOFF2 with FontTools; small UI subsets are accompanied by full-character font files. CSS unicode ranges select the small subsets for current interface text and use the full fonts for other supported characters. No CJK glyphs were replaced by a different typeface.

The modified Source Han Sans web fonts use the internal family name **Model Watch CJK** to respect the upstream reserved font name. The glyph designs remain those of Source Han Sans SC. JetBrains Mono retains its family name.

Font files are committed assets; GitHub Actions does not need to download or build them.

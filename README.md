# Android Intent Extra Mapper

A lightweight Python static-analysis tool for JADX output. It identifies exported Android activities and searches `onCreate()` and `onNewIntent()` for common Intent extra getters, then generates a Markdown report.

## Requirements

- Python 3.9+
- JADX decompiled output containing `resources/AndroidManifest.xml` and `sources/`
- No third-party Python packages

## Installation

Clone the repository:

```bash
git clone https://github.com/Cookies307/Android-Intent-Extra-Mapper.git
```

Navigate to the project directory:

```bash
cd Android-Intent-Extra-Mapper
```

Run the tool:

```bash
python intent_extra_mapper.py -InputPath "path\to\jadx-output"
```

## Usage

```powershell
python .\intent_extra_mapper.py -InputPath "D:\path\to\jadx-output"
```

The report is saved as `Intent-Extras-Report.md` inside the JADX output directory.

Choose a custom report path:

```powershell
python .\intent_extra_mapper.py -InputPath "D:\path\to\jadx-output" -OutputPath "D:\Reports\intent-extras.md"
```

If the manifest is outside the input directory:

```powershell
python .\intent_extra_mapper.py -InputPath "D:\path\to\jadx-output" -ManifestPath "D:\path\to\AndroidManifest.xml"
```

## What it detects

Supports common getters including `getStringExtra`, `getIntExtra`, `getBooleanExtra`, `getLongExtra`, `getBundleExtra`, `getParcelableExtra`, `getSerializableExtra`, and array/list variants. `getExtras()` is reported as a Bundle requiring manual review.

The Markdown report includes exported component details, source class, method scope, extra key, inferred type, getter, confidence, and scan summary.

## Limitations

- Static analysis only; it does not execute the app or send Intents.
- It primarily analyzes direct getter calls inside `onCreate()` and `onNewIntent()`.
- It may miss extras read in helper methods, wrappers, reflection, indirect data flows, or dynamically constructed keys.
- Constant names such as `EXTRA_USERNAME` are reported as identifiers, not resolved to their definitions.
- "No extras detected" is not proof that the Activity never consumes Intent data.
- Review exported status and activity aliases manually when needed.

## Workflow

1. Decompile the APK with JADX.
2. Run this tool against the JADX output folder.
3. Open `Intent-Extras-Report.md`.
4. Review detected keys and test expected, missing, malformed, and unexpected values within your authorized assessment scope.

A detected extra is an analysis lead, not a vulnerability by itself.

## License

MIT License. See [LICENSE](LICENSE).

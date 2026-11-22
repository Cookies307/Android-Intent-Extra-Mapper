# Android Intent Extra Mapper

A lightweight Python static-analysis helper for JADX output. It reads `AndroidManifest.xml`, identifies exported activities, and searches their `onCreate()` and `onNewIntent()` methods for common Intent extra getters.

## Requirements

- Python 3.9+
- JADX decompiled output (including `resources/AndroidManifest.xml` and `sources/`)

No third-party Python packages are required.

## Usage

```powershell
python .\intent_extra_mapper.py -InputPath "D:\path\to\jadx-output"
```

Choose a custom report path:

```powershell
python .\intent_extra_mapper.py -InputPath "D:\path\to\jadx-output" -OutputPath "D:\Reports\intent-extras.csv"
```

If the manifest is outside the input directory:

```powershell
python .\intent_extra_mapper.py -InputPath "D:\path\to\jadx-output" -ManifestPath "D:\path\to\AndroidManifest.xml"
```

The CSV report includes the exported component, corresponding source class, method scope, extra key, inferred type, getter method, and key confidence.

## Supported getters

Includes common methods such as `getStringExtra`, `getIntExtra`, `getBooleanExtra`, `getLongExtra`, `getBundleExtra`, `getParcelableExtra`, `getSerializableExtra`, and array/list variants. `getExtras()` is reported as a Bundle requiring manual review.

## Limitations

- Static analysis only; it does not execute the app or send Intents.
- It primarily analyzes direct getter calls inside `onCreate()` and `onNewIntent()`.
- It may miss extras read in helper methods, wrappers, reflection, indirect data flows, or dynamically constructed keys.
- Constant names such as `EXTRA_USERNAME` are reported as identifiers, not resolved to their definitions.
- "No extras detected" means no supported getter was found in those two lifecycle methods; it is not proof that the Activity never consumes Intent data.
- Exported status is inferred from the decoded manifest and target SDK. Review unusual manifests and activity aliases manually.

## Workflow

1. Decompile the APK with JADX.
2. Run this tool against the JADX output folder.
3. Review `Intent-Extras-Report.csv`.
4. For detected keys, test expected, missing, malformed, and unexpected values within your authorized assessment scope.
5. For rows with no extras detected, continue with the next step in your testing methodology.

A detected extra is an analysis lead, not a vulnerability by itself.

## License

MIT License. See [LICENSE](LICENSE).

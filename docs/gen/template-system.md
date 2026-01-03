# Template System

The template system provides project scaffolding for apps, Rocky.js watchfaces, and libraries.

## Overview

**Location:** `pebble_tool/sdk/templates/`

**Template Types:**
- **app** - C-based applications and watchfaces
- **rocky** - Rocky.js JavaScript watchfaces
- **lib** - Reusable library packages

**Configuration:** JSON-driven with variable substitution

## Directory Structure

```
templates/
├── templates.json          # Central configuration
├── common/                 # Shared components
│   └── gitignore          # Common .gitignore
├── app/                   # App templates
│   ├── main.c             # Full app with UI
│   ├── simple.c           # Minimal app
│   ├── worker.c           # Background worker
│   ├── index.js           # PebbleKit JS
│   ├── package.json       # NPM config
│   ├── wscript            # Build script
│   └── ai.md              # AI assistant docs
├── rocky/                 # Rocky.js templates
│   ├── index.js           # Rocky watchface
│   ├── app.js             # PebbleKit JS
│   ├── package.json       # Rocky config
│   └── wscript            # Build script
└── lib/                   # Library templates
    ├── lib.c              # C implementation
    ├── lib.h              # C header
    ├── lib.js             # JS library
    ├── package.json       # Library config
    └── wscript            # Build script
```

## Template Configuration

**File:** `pebble_tool/sdk/templates/templates.json`

### Configuration Structure

```json
{
    "default": {
        ".gitignore": "gitignore"
    },
    "rocky": {
        "default": {
            "src/pkjs/index.js": "rocky/app.js",
            "src/rocky/index.js": "rocky/index.js",
            "wscript": "rocky/wscript",
            "package.json": "rocky/package.json"
        }
    },
    "app": {
        "default": {
            "src/c/${project_name}.c": "app/main.c",
            "wscript": "app/wscript",
            "package.json": "app/package.json",
            "resources": null
        },
        "worker": {
            "worker_src/c/${project_name}_worker.c": "app/worker.c"
        },
        "simple": {
            "src/c/${project_name}.c": "app/simple.c"
        },
        "javascript": {
            "src/pkjs/index.js": "app/index.js"
        },
        "ai": {
            "CLAUDE.md": "app/ai.md",
            ".cursor/rules/pebble.mdc": "app/ai.md"
        }
    },
    "lib": {
        "default": {
            "src/c/${project_name}.c": "lib/lib.c",
            "include/${project_name}.h": "lib/lib.h",
            "wscript": "lib/wscript",
            "package.json": "lib/package.json",
            "src/resources": null
        },
        "javascript": {
            "src/js/index.js": "lib/lib.js"
        }
    }
}
```

**Structure:**
- **Top-level "default"** - Applied to all project types
- **Project type keys** - "app", "rocky", "lib"
- **Sub-options** - "default" (required), "worker", "simple", etc.
- **Mapping format** - `"destination/path": "template/source"`
- **Directory creation** - `"directory": null` creates empty dir
- **Variable substitution** - Paths can contain `${variable}` placeholders

## Template Selection

**File:** `pebble_tool/commands/sdk/create.py`

### NewProjectCommand

**Function:** `__call__()` (create.py:140-164)

```python
def __call__(self, args):
    self.get_sdk_path()  # Ensure SDK installed

    sdk = self.sdk or sdk_version()
    sdk2 = (sdk == "2.9")

    if args.rocky:
        if sdk2:
            raise ToolError("--rocky not compatible with SDK 2.9")
        if args.simple or args.worker:
            raise ToolError("--rocky incompatible with --simple and --worker")
        options = ['rocky']
    else:
        options = ['app']
        if args.javascript:
            options.append('javascript')
        if args.simple:
            options.append('simple')
        if args.worker:
            options.append('worker')
        if args.ai:
            options.append('ai')
```

**Options Array:**
- First element: project type ('app', 'rocky', or 'lib')
- Subsequent elements: additional features

### NewPackageCommand

**Function:** `__call__()` (create.py:189-218)

```python
def __call__(self, args):
    options = ["lib"]
    if args.javascript:
        options.append("javascript")

    _copy_from_template(template_layout, template_path, args.name, options)
```

## Variable Substitution

**Function:** `substitute()` (create.py:75-80)

```python
def substitute(template_content):
    return Template(template_content).substitute(
        uuid=str(uuid),
        project_name=project_name,
        display_name=project_name,
        project_name_c=re.sub(r'[^a-zA-Z0-9_]+', '_', project_name),
        sdk_version=SDK_VERSION
    )
```

**Available Variables:**
- `${uuid}` - Unique UUID (generated via `uuid4()`)
- `${project_name}` - Project name from command line
- `${display_name}` - Display name (same as project_name)
- `${project_name_c}` - C-safe identifier (non-alphanumeric → underscores)
- `${sdk_version}` - Current SDK version

**Usage Examples:**

**In package.json:**
```json
{
  "name": "${project_name}",
  "pebble": {
    "uuid": "${uuid}",
    "displayName": "${display_name}",
    "sdkVersion": "${sdk_version}"
  }
}
```

**In file paths:**
```
"src/c/${project_name}.c": "app/main.c"
```

**In C code:**
```c
#include "${project_name}.h"

bool ${project_name_c}_find_truth(void) {
    return true;
}
```

## Template Processing

**Function:** `_copy_from_template()` (create.py:50-120)

### Processing Logic

```python
def copy_group(group, must_succeed=True):
    copied_files = 0

    for dest, origins in iteritems(group):
        target_path = os.path.join(substitute(project_root), dest)

        # Create empty directory if origins is None
        if origins is None:
            _mkdirs(target_path)
            continue

        # Handle single or multiple source files
        if isinstance(origins, string_types):
            origins = [origins]

        # Find first existing template file
        origin_path = extant_path(os.path.join(template_root, x) for x in origins)
        if origin_path is not None:
            copied_files += 1
            _mkdirs(target_path)

            # Read template, substitute variables, write to destination
            with open(origin_path) as f:
                template_content = f.read()
            with open(substitute(target_path), 'w') as f:
                f.write(substitute(template_content))

    if must_succeed and copied_files == 0:
        raise ToolError("Can't create that sort of project with the current SDK.")
```

### Application Order

```python
try:
    copy_group(template.get('default', {}), must_succeed=False)  # Common files
    copy_group(template.get(options[0], {}).get('default', {}))  # Project type
    for option in options[1:]:
        copy_group(template.get(options[0], {}).get(option, {}))  # Features
except Exception:
    shutil.rmtree(project_root)  # Cleanup on failure
    raise
```

**Order:**
1. Top-level "default" (e.g., .gitignore)
2. Project type "default" (e.g., app.default)
3. Each additional option (e.g., app.javascript, app.worker)

## Template Examples

### App Template (main.c)

**File:** `pebble_tool/sdk/templates/app/main.c`

Full UI example with:
- Window with TextLayer
- Button click handlers (UP, DOWN, SELECT)
- Complete lifecycle management

### Simple Template (simple.c)

**File:** `pebble_tool/sdk/templates/app/simple.c`

```c
#include <pebble.h>

int main(void) {
  app_event_loop();
}
```

Minimal starting point.

### Worker Template (worker.c)

**File:** `pebble_tool/sdk/templates/app/worker.c`

```c
#include <pebble_worker.h>

int main(void) {
  worker_event_loop();
}
```

Background worker process.

### JavaScript Template (index.js)

**File:** `pebble_tool/sdk/templates/app/index.js`

```javascript
Pebble.addEventListener("ready",
    function(e) {
        console.log("Hello world! - Sent from your javascript application.");
    }
);
```

### Rocky.js Template (index.js)

**File:** `pebble_tool/sdk/templates/rocky/index.js`

Complete watchface with:
- Time and date display
- Minute change event handling
- Canvas drawing with fonts
- Message passing to phone

### Library Templates

**C Library (lib.c, lib.h):**
- Uses `${project_name_c}` for function names
- Proper header inclusion with substitution
- Example function implementation

**JS Library (lib.js):**
```javascript
var run_me = function(e) {
    console.log("Look at me, I'm running!");
};

module.exports = run_me;
```

## Shared Components

**File:** `pebble_tool/sdk/templates/common/gitignore`

**Content:**
```
# Ignore build generated files
build/
dist/
dist.zip

# Ignore waf lock file
.lock-waf*

# Ignore installed node modules
node_modules/
```

Applied to all projects via top-level "default" section.

## Project Creation Flow

**Example:** `pebble new-project myapp --javascript --ai`

**Steps:**

1. **Parse Options** → `options = ['app', 'javascript', 'ai']`

2. **Create Directory** → `/path/to/myapp/`

3. **Apply "default"** (top-level)
   - Create `.gitignore` from `common/gitignore`

4. **Apply "app.default"**
   - Create `src/c/myapp.c` from `app/main.c`
   - Create `wscript` from `app/wscript`
   - Create `package.json` with substitutions:
     ```json
     {
       "name": "myapp",
       "pebble": {
         "displayName": "myapp",
         "uuid": "12345678-1234-1234-1234-123456789abc",
         "sdkVersion": "3"
       }
     }
     ```
   - Create empty `resources/` directory

5. **Apply "app.javascript"**
   - Create `src/pkjs/index.js` from `app/index.js`

6. **Apply "app.ai"**
   - Create `CLAUDE.md` from `app/ai.md`
   - Create `.cursor/rules/pebble.mdc` from `app/ai.md`

7. **Post Analytics**
   ```python
   post_event("sdk_create_project", javascript=True, worker=False, rocky=False)
   ```

## Helper Functions

**Template Resolution:** `extant_path()` (create.py:35-47)

```python
def extant_path(paths):
    """Returns first path that exists, or None"""
    for path in paths:
        if os.path.exists(path):
            return path
    return None
```

Enables template fallback - tries multiple locations.

## Command Examples

```bash
# Create app project
pebble new-project myapp

# Create app with JavaScript
pebble new-project myapp --javascript

# Create app with worker
pebble new-project myapp --worker

# Create simple app
pebble new-project myapp --simple

# Create with AI docs
pebble new-project myapp --ai

# Create Rocky.js watchface
pebble new-project mywatchface --rocky

# Create library
pebble new-package mylib

# Create library with JavaScript
pebble new-package mylib --javascript
```

## Summary

The template system provides:
- **JSON-Driven Configuration** - Declarative template definitions
- **Variable Substitution** - Python's string.Template for flexibility
- **Hierarchical Application** - default → type → options
- **Multiple Template Types** - app, rocky, lib
- **Feature Composition** - Combine options (javascript, worker, ai)
- **Flexible Resolution** - Fallback mechanisms via extant_path()
- **Error Handling** - Automatic cleanup on failure
- **Path Substitution** - Variables in both paths and content

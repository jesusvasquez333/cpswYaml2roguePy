# cpswYaml2roguePy
Script to convert CPSW YAML to Rogue Python classes

## How to use it
```{r, engine='bash', usage}
Usage: python yaml2py.py [-h|--help] -M|--module module_name -t|--title module_title  [-D|--dir yaml_dir] [-D|--description module_description]
    -h|--help                           : show this message
    -D|--dir yaml_dir                   : Yaml file directory
    -M|--module module_name             : module name
    -t|--title module_title             : module title to write on the file header
    -d|--description module_description : module description to write on the file header.
                                          If empty, the title will be used as description.
```
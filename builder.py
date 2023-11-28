import yaml


# Define a custom constructor for the !Ref tag
def ref_constructor(loader, node):
    value = loader.construct_scalar(node)
    return value  # You can define the behavior for !Ref as needed


# Add the custom constructor to the YAML loader
yaml.SafeLoader.add_constructor("!Ref", ref_constructor)


# Define a custom constructor for the !Sub tag
def sub_constructor(loader, node):
    value = loader.construct_scalar(node)
    return value  # You can define the behavior for !Sub as needed


# Add the custom constructor to the YAML loader
yaml.SafeLoader.add_constructor("!Sub", sub_constructor)


def add_environment_variable(
    template_path, function_name, variable_name, variable_value
):
    with open(template_path, "r") as file:
        template = yaml.safe_load(file)

    if "Resources" in template and function_name in template["Resources"]:
        function = template["Resources"][function_name]
        if "Properties" in function and "Environment" in function["Properties"]:
            if "Variables" not in function["Properties"]["Environment"]:
                function["Properties"]["Environment"]["Variables"] = {}
            function["Properties"]["Environment"]["Variables"][
                variable_name
            ] = variable_value
        if "Properties" in function and "Environment" not in function["Properties"]:
            # then create an empty dictionary for environment variables
            function["Properties"]["Environment"] = {}
            function["Properties"]["Environment"]["Variables"] = {}
            function["Properties"]["Environment"]["Variables"][
                variable_name
            ] = variable_value

    with open(template_path, "w") as file:
        yaml.dump(template, file)


# Usage example
template_path = "template.yml"
function_name = "weather"  # Replace with your function's name
variable_name = "MY_VARIABLE"  # New environment variable name
variable_value = "my_variable_value"  # New environment variable value

if __name__ == "__main__":
    # This block of code will execute when the script is run directly
    # Call your functions or include your logic here

    add_environment_variable(
        template_path, function_name, variable_name, variable_value
    )

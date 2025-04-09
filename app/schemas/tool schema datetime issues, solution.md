Key Features of the Final Solution

Compatible Type Handling:

Used Any type for all date/datetime fields to avoid type annotation issues
Added field descriptions to all fields for API documentation
Added runtime validators to ensure correct types


Pydantic v2 Compatible Validators:

Used @field_validator decorator (instead of @validator)
Added @classmethod to all validator methods
Updated parameter handling to use info.field_name and info.data


Complete Validation:

Added constraints like ge=0 for numeric fields
Added gt=0 for maintenance intervals
Added validators for all date/datetime fields


Comprehensive Documentation:

Restored all field descriptions
Maintained the module docstring
Added proper documentation for each model class



What Makes This Solution Work
The key insight was that the specific combination of Optional[date] with Field() was causing conflicts in your Pydantic v2 environment. By using Any type while maintaining runtime validation, we get the best of both worlds:

The schema starts up without errors
Runtime validation ensures that only valid date/datetime objects are accepted
All the field constraints and descriptions work properly
Your API documentation will be complete and useful

Lessons Learned
This process demonstrated that sometimes type annotations can cause compatibility issues, especially when libraries evolve. Using runtime validation as a backup strategy allows us to maintain strong typing guarantees while avoiding these compatibility problems.
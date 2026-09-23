"""
These are shared Models that every single areas schemas.py can make use of instead of everyone repeating it themselves.

Please add more to this file if you think its applicable.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

"""
Based on our data model and the standards we learnt in database systems we use CamelCase for all of our vairables.
For that reason I did the same with our JSON database. However, as python devs we are all much more used to camel case.

I looked up what people do in cases like these and so I created my own model using pydantic to be able to convert
to camel case for us!

All of our classes will inherent from this, making them a model / class with the ability to translate between camel and snake case
"""


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        # allows us to construct these with snake case field names in our code
        populate_by_name=True,
    )


"""
A single refernece to any user (creator, volunteer, organisation)
"""


class UserRef(CamelModel):
    user_id: str
    name: str

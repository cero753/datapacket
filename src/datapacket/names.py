"""Name pools for the synthetic firm. Nicknames are the point: one person shows up
as Joseph, Joe, Joey and "Joe D" across systems, and the identity graph has to
fold them back into one canonical ID."""

NICKNAMES: dict[str, list[str]] = {
    "Joseph": ["Joe", "Joey"], "Robert": ["Bob", "Rob"], "William": ["Bill", "Will"],
    "Elizabeth": ["Liz", "Beth"], "Katherine": ["Kate", "Katie"], "Michael": ["Mike"],
    "James": ["Jim", "Jamie"], "Margaret": ["Maggie", "Peggy"], "Richard": ["Rick"],
    "Thomas": ["Tom"], "Daniel": ["Dan"], "Christopher": ["Chris"], "Jennifer": ["Jen"],
    "Patricia": ["Pat", "Trish"], "Anthony": ["Tony"], "Steven": ["Steve"],
    "Andrew": ["Andy", "Drew"], "Nicholas": ["Nick"], "Alexander": ["Alex"],
    "Samantha": ["Sam"], "Benjamin": ["Ben"], "Matthew": ["Matt"], "Jonathan": ["Jon"],
    "Susan": ["Sue"], "Deborah": ["Deb"], "Edward": ["Ed", "Ted"], "Charles": ["Chuck", "Charlie"],
    "Timothy": ["Tim"], "Rebecca": ["Becky"], "Victoria": ["Vicky"], "Gregory": ["Greg"],
    "Priya": [], "Wei": [], "Carlos": [], "Fatima": [], "Olivia": ["Liv"], "Ethan": [],
    "Hannah": [], "Marcus": [], "Sofia": [], "Diego": [], "Aisha": [], "Noah": [],
    "Grace": [], "Isaac": ["Ike"], "Leah": [], "Owen": [], "Ruth": [], "Simon": [],
}

LAST_NAMES = [
    "Marlowe", "Halvorsen", "Pike", "Okafor", "Brennan", "Castellano", "Whitaker", "Nguyen",
    "Lindqvist", "Ramirez", "Kowalski", "Fitzgerald", "Abernathy", "Sato", "Mendoza",
    "Gallagher", "Petrov", "Osei", "Hargrove", "Delacroix", "Yamamoto", "Barrett",
    "Szabo", "Ferreira", "Mcallister", "Novak", "Quintero", "Ashworth", "Bianchi",
    "Thornton", "Iyer", "Holloway", "Kensington", "Vasquez", "Lindgren", "Prescott",
    "Moreau", "Draper", "Achebe", "Sorensen", "Kaplan", "Winslow", "Estrada", "Rourke",
    "Hendricks", "Marchetti", "Calloway", "Pembroke", "Strand", "Oyelaran",
]

# Aliases that are also ordinary English words. A naive scrubber redacts "Will you
# send..." and "Pat the drawings dry"; ours only redacts these in name position.
AMBIGUOUS = {"Will", "Bill", "Pat", "Rob", "Sue", "Drew", "Chuck", "Ted", "Jim", "Grace",
             "Ruth", "Sam", "Ben", "Jon", "Ike", "Liv", "Deb", "Ed", "Tim", "Jen"}

CLIENTS = [
    "Marrowfield Health System", "Copper Basin School District", "Lakeview Senior Living",
    "Northgate Logistics", "St. Brigid Parish", "Ridgeline Credit Union", "Harbor Point Hotels",
    "Tamarack County", "Ellison Biotech", "Fairhaven Public Library", "Summit Ridge Apartments",
    "Blue Heron Marina",
]

# People who appear only in free text (inspectors, neighbours, subcontractor staff).
# They are in no roster or CRM, so only a statistical NER layer can catch them.
UNLISTED_PEOPLE = [
    "Harold Brecken", "Dolores Amsel", "Vincent Okoro", "Mabel Trudeau", "Franklin Voss",
    "Imogen Castell", "Rudy Pfister", "Celeste Wakefield", "Bernard Ilić", "Nadia Orlov",
    "Lionel Hatch", "Greta Sundqvist", "Mateo Arguello", "Eleanor Quayle", "Arjun Mehra",
]

ROLES = (["Principal"] * 4 + ["Project Manager"] * 22 + ["Project Architect"] * 40
         + ["Designer"] * 60 + ["CAD Technician"] * 30 + ["Interior Designer"] * 14
         + ["Office Manager"] * 3 + ["HR Generalist"] * 3 + ["Accountant"] * 6
         + ["IT Admin"] * 4 + ["Marketing Coordinator"] * 4 + ["Spec Writer"] * 10)
assert len(ROLES) == 200

STREETS = ["Maple Ave", "Cedar Ln", "Ridge Rd", "Lakeshore Dr", "Birch St", "Quarry Rd",
           "Orchard Way", "Mill St", "Highland Ave", "Willow Ct"]
CITIES = [("Duluth", "MN"), ("Rochester", "NY"), ("Boise", "ID"), ("Fort Wayne", "IN"),
          ("Spokane", "WA"), ("Akron", "OH")]

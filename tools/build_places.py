"""Widen the place list so an operator anywhere gets useful neighbours.

Names are ordinary knowledge; every coordinate comes from Nominatim, so
nothing here is remembered rather than looked up. Existing entries are kept
from the cache, so this is cheap to re-run.

Run it from the repository root:  python3 tools/build_places.py
It rewrites data/places.json, the bundled fallback list used when a
unit has no internet and cannot fetch neighbours from Overpass.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elmer import geocode

CITIES = """
Seattle WA|Spokane WA|Tacoma WA|Yakima WA|Bellingham WA|Olympia WA|Vancouver WA
Portland OR|Eugene OR|Salem OR|Medford OR|Bend OR|Pendleton OR
Boise ID|Idaho Falls ID|Coeur d'Alene ID|Twin Falls ID|Pocatello ID
Billings MT|Missoula MT|Great Falls MT|Bozeman MT|Helena MT|Kalispell MT|Glendive MT
Casper WY|Cheyenne WY|Sheridan WY|Rock Springs WY
Fargo ND|Bismarck ND|Grand Forks ND|Minot ND|Williston ND|Dickinson ND
Sioux Falls SD|Rapid City SD|Aberdeen SD|Pierre SD|Watertown SD
Minneapolis MN|Saint Paul MN|Duluth MN|Rochester MN|Mankato MN|Saint Cloud MN
Bemidji MN|Brainerd MN|Moorhead MN|Alexandria MN|Winona MN|Hibbing MN
Des Moines IA|Cedar Rapids IA|Davenport IA|Sioux City IA|Waterloo IA|Dubuque IA|Council Bluffs IA
Omaha NE|Lincoln NE|Grand Island NE|North Platte NE|Scottsbluff NE|Kearney NE
Kansas City MO|Saint Louis MO|Springfield MO|Columbia MO|Joplin MO|Cape Girardeau MO
Wichita KS|Topeka KS|Salina KS|Dodge City KS|Hays KS|Lawrence KS
Oklahoma City OK|Tulsa OK|Lawton OK|Enid OK|Woodward OK|McAlester OK
Dallas TX|Fort Worth TX|Houston TX|San Antonio TX|Austin TX|El Paso TX|Lubbock TX
Amarillo TX|Waco TX|Tyler TX|Abilene TX|Midland TX|Corpus Christi TX|Laredo TX
Beaumont TX|Wichita Falls TX|San Angelo TX|Brownsville TX|College Station TX
Denver CO|Colorado Springs CO|Pueblo CO|Grand Junction CO|Fort Collins CO|Durango CO|Alamosa CO
Salt Lake City UT|Provo UT|Ogden UT|Saint George UT|Moab UT|Cedar City UT
Albuquerque NM|Santa Fe NM|Las Cruces NM|Roswell NM|Farmington NM|Clovis NM
Phoenix AZ|Tucson AZ|Flagstaff AZ|Yuma AZ|Prescott AZ|Sierra Vista AZ
Las Vegas NV|Reno NV|Elko NV|Ely NV|Winnemucca NV
Los Angeles CA|San Diego CA|San Francisco CA|Sacramento CA|Fresno CA|San Jose CA
Bakersfield CA|Eureka CA|Redding CA|Santa Barbara CA|Palm Springs CA|Barstow CA
Monterey CA|Chico CA|Stockton CA|Riverside CA
Chicago IL|Peoria IL|Springfield IL|Rockford IL|Champaign IL|Carbondale IL|Quincy IL
Milwaukee WI|Madison WI|Green Bay WI|Eau Claire WI|La Crosse WI|Wausau WI|Superior WI
Detroit MI|Grand Rapids MI|Lansing MI|Marquette MI|Traverse City MI|Saginaw MI|Sault Ste. Marie MI
Indianapolis IN|Fort Wayne IN|Evansville IN|South Bend IN|Terre Haute IN|Bloomington IN
Columbus OH|Cleveland OH|Cincinnati OH|Toledo OH|Dayton OH|Youngstown OH|Athens OH
Louisville KY|Lexington KY|Bowling Green KY|Paducah KY|Ashland KY
Nashville TN|Memphis TN|Knoxville TN|Chattanooga TN|Jackson TN|Johnson City TN
Birmingham AL|Montgomery AL|Mobile AL|Huntsville AL|Dothan AL|Tuscaloosa AL
Atlanta GA|Savannah GA|Augusta GA|Columbus GA|Macon GA|Albany GA|Valdosta GA
Jacksonville FL|Orlando FL|Miami FL|Tampa FL|Tallahassee FL|Fort Myers FL|Pensacola FL|Key West FL
Charlotte NC|Raleigh NC|Greensboro NC|Asheville NC|Wilmington NC|Fayetteville NC
Charleston SC|Columbia SC|Greenville SC|Myrtle Beach SC
Richmond VA|Norfolk VA|Roanoke VA|Charlottesville VA|Bristol VA
Washington DC|Baltimore MD|Salisbury MD|Cumberland MD|Dover DE
Philadelphia PA|Pittsburgh PA|Harrisburg PA|Erie PA|Scranton PA|Williamsport PA|Allentown PA
Buffalo NY|Syracuse NY|New York NY|Albany NY|Rochester NY|Binghamton NY|Watertown NY|Plattsburgh NY
Boston MA|Worcester MA|Springfield MA|Hyannis MA|Pittsfield MA
Portland ME|Bangor ME|Presque Isle ME|Augusta ME
Burlington VT|Rutland VT|Concord NH|Berlin NH|Hartford CT|New Haven CT|Providence RI
Charleston WV|Huntington WV|Morgantown WV|Beckley WV|Clarksburg WV
Little Rock AR|Fayetteville AR|Fort Smith AR|Jonesboro AR|Texarkana AR
New Orleans LA|Baton Rouge LA|Shreveport LA|Lafayette LA|Monroe LA|Lake Charles LA
Jackson MS|Gulfport MS|Tupelo MS|Meridian MS|Greenville MS
Anchorage AK|Fairbanks AK|Juneau AK|Ketchikan AK|Kodiak AK|Nome AK|Bethel AK|Homer AK
Sitka AK|Valdez AK|Utqiagvik AK|Dillingham AK
Honolulu HI|Hilo HI|Kahului HI|Lihue HI|Kailua-Kona HI|Waimea HI
Winnipeg MB|Brandon MB|Thunder Bay ON|Toronto ON|Ottawa ON|London ON|Sudbury ON|Kenora ON
Montreal QC|Quebec City QC|Sherbrooke QC|Halifax NS|Moncton NB|St John's NL
Regina SK|Saskatoon SK|Calgary AB|Edmonton AB|Lethbridge AB|Vancouver BC|Victoria BC
Kelowna BC|Prince George BC|Whitehorse YT|Yellowknife NT
Tijuana MX|Monterrey MX|Ciudad Juarez MX|Chihuahua MX|Hermosillo MX|Mexico City MX
Nassau BS|Havana CU|San Juan PR|Hamilton BM
""".replace("\n", "|").strip("|")

names = [c.strip() for c in CITIES.split("|") if c.strip()]
seen, out, missed = set(), [], []
for n, name in enumerate(names, 1):
    if name in seen:
        continue
    seen.add(name)
    place = geocode.resolve(name)
    if place and place.get("lat") is not None:
        label, region = name.rsplit(" ", 1)
        out.append({"name": label, "region": region,
                    "lat": round(place["lat"], 4), "lon": round(place["lon"], 4)})
    else:
        missed.append(name)
    if n % 50 == 0:
        print(f"  {n}/{len(names)}...", file=sys.stderr, flush=True)

json.dump({"note": "Coordinates from OpenStreetMap Nominatim; the names are "
                   "ordinary knowledge. Used to name what an antenna can "
                   "actually reach from where the operator is.",
           "places": sorted(out, key=lambda p: (p["region"], p["name"]))},
          open(ROOT / "data" / "places.json", "w"), indent=1)
print(f"wrote {len(out)} places; could not resolve {len(missed)}: {missed[:10]}")

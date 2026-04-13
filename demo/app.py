"""psgc visual demo — run with: python demo/app.py"""

from __future__ import annotations

import html
import json
import os
import sys
import http.server
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import psgc

PORT = 8888


class DemoHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            self._html(self._index_page())
        elif path == "/api/search":
            self._json(self._api_search(params))
        elif path == "/api/suggest":
            self._json(self._api_suggest(params))
        elif path == "/api/get":
            self._json(self._api_get(params))
        elif path == "/api/nearest":
            self._json(self._api_nearest(params))
        elif path == "/api/reverse":
            self._json(self._api_reverse(params))
        elif path == "/api/distance":
            self._json(self._api_distance(params))
        elif path == "/api/parse":
            self._json(self._api_parse(params))
        elif path == "/api/stats":
            self._json(self._api_stats())
        elif path == "/api/regions":
            self._json(self._api_regions())
        elif path == "/api/geojson":
            self._json(self._api_geojson(params))
        elif path == "/api/profile":
            self._json(self._api_profile(params))
        elif path == "/api/children":
            self._json(self._api_children(params))
        else:
            self.send_error(404)

    def _html(self, content: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode())

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode())

    def _api_search(self, params):
        q = params.get("q", [""])[0]
        n = int(params.get("n", ["10"])[0])
        threshold = float(params.get("threshold", ["60"])[0])
        phonetic = params.get("phonetic", [""])[0] == "1"
        hooks = params.get("hooks", [""])[0].split(",") if params.get("hooks", [""])[0] else None
        results = psgc.search(q, n=n, threshold=threshold, phonetic=phonetic, match_hooks=hooks)

        q_lower = q.lower().strip()
        def _boost(r):
            name_lower = r.place.name.lower()
            city_match = (name_lower == f"city of {q_lower}"
                          or name_lower == f"{q_lower} city"
                          or name_lower == q_lower)
            is_higher_level = r.level in ("city", "province", "region")
            return (not (city_match and is_higher_level), -r.score)
        results = sorted(results, key=_boost)

        out = []
        for r in results:
            d = r.to_dict()
            d["population"] = r.place.population
            out.append(d)
        return out

    def _api_suggest(self, params):
        q = params.get("q", [""])[0]
        return psgc.suggest(q, limit=10)

    def _api_get(self, params):
        q = params.get("q", [""])[0]
        try:
            place = psgc.get(q)
            d = place.to_dict()
            d["breadcrumb"] = place.breadcrumb
            if hasattr(place, "population_density") and place.population_density:
                d["population_density"] = round(place.population_density, 1)
            if hasattr(place, "parent"):
                d["parent_name"] = place.parent.name
            if hasattr(place, "children"):
                d["children_count"] = len(place.children)
            if hasattr(place, "siblings"):
                d["siblings_count"] = len(place.siblings)
            if hasattr(place, "sub_municipalities"):
                subs = place.sub_municipalities
                if subs:
                    d["sub_municipalities"] = [
                        {"name": s.name, "psgc_code": s.psgc_code,
                         "barangay_count": len(s.children)}
                        for s in subs
                    ]
            return {"ok": True, "place": d}
        except psgc.AmbiguousLookupError as e:
            return {"ok": False, "error": "ambiguous", "message": str(e),
                    "matches": [{"name": m.name, "psgc_code": m.psgc_code,
                                 "parent": m.parent.name if hasattr(m, "city_code") else None}
                                for m in e.matches]}
        except LookupError as e:
            return {"ok": False, "error": "not_found", "message": str(e)}

    def _api_nearest(self, params):
        lat = float(params.get("lat", ["14.5995"])[0])
        lng = float(params.get("lng", ["120.9842"])[0])
        n = int(params.get("n", ["10"])[0])
        results = psgc.nearest(lat, lng, n=n)
        return [r.to_dict() for r in results]

    def _api_reverse(self, params):
        lat = float(params.get("lat", ["14.5995"])[0])
        lng = float(params.get("lng", ["120.9842"])[0])
        result = psgc.reverse_geocode(lat, lng)
        return result.to_dict()

    def _api_distance(self, params):
        a = params.get("a", [""])[0]
        b = params.get("b", [""])[0]
        try:
            d = psgc.distance(a, b)
            pa = psgc.get(a)
            pb = psgc.get(b)
            return {"ok": True, "distance_km": d, "a": pa.name, "b": pb.name,
                    "a_coord": pa.coordinate.to_dict() if pa.coordinate else None,
                    "b_coord": pb.coordinate.to_dict() if pb.coordinate else None}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _api_children(self, params):
        code = params.get("code", [""])[0]
        level = params.get("level", [""])[0]
        from psgc._loader import get_store
        store = get_store()

        if level == "province":
            children = store.provinces_by_region(code)
            children = [c for c in children if c.psgc_code != code]
        elif level == "city":
            children = store.cities_by_province(code)
            if not children:
                children = [c for c in store.cities
                            if c.region_code == code and c.geographic_level != "SubMun"]
        elif level == "barangay":
            try:
                city = store.get_city(code)
                children = city.barangays
            except KeyError:
                children = []
        else:
            children = []

        return [{"psgc_code": c.psgc_code, "name": c.name,
                 "population": c.population,
                 "latitude": c.coordinate.latitude if c.coordinate else None,
                 "longitude": c.coordinate.longitude if c.coordinate else None,
                 "level": getattr(c, "geographic_level", None)}
                for c in children]

    def _api_profile(self, params):
        """Rich contextual profile for a place."""
        code = params.get("code", [""])[0]
        from psgc._loader import get_store
        store = get_store()

        try:
            for getter, level in [(store.get_barangay, "barangay"), (store.get_city, "city"),
                                  (store.get_region, "region"), (store.get_province, "province")]:
                try:
                    place = getter(code)
                    break
                except KeyError:
                    continue
            else:
                return {"ok": False}
        except Exception:
            return {"ok": False}

        result = {
            "ok": True,
            "name": place.name,
            "psgc_code": place.psgc_code,
            "level": level,
            "population": place.population,
            "coordinate": place.coordinate.to_dict() if place.coordinate else None,
        }

        sentences = []

        if level == "barangay":
            city = store.get_city(place.city_code)
            prov = store.get_province(place.province_code)
            reg = store.get_region(place.region_code)

            kind = "an urban" if place.urban_rural == "U" else "a rural" if place.urban_rural == "R" else "a"
            sentences.append(f"{place.name} is {kind} barangay in {city.name}, {reg.name}.")

            if place.population:
                siblings = store.barangays_by_city(place.city_code)
                siblings_with_pop = sorted([b for b in siblings if b.population], key=lambda b: b.population, reverse=True)
                rank = next((i+1 for i, b in enumerate(siblings_with_pop) if b.psgc_code == place.psgc_code), None)
                total = len(siblings)
                if rank and total > 1:
                    if rank == 1:
                        sentences.append(f"It is the most populous of {total} barangays in {city.name}.")
                    elif rank <= 3:
                        sentences.append(f"It ranks #{rank} out of {total} barangays in {city.name} by population.")
                    elif rank > total - 3:
                        sentences.append(f"It is among the smallest of {total} barangays in {city.name}.")

                if city.population and city.population > 0:
                    pct = place.population / city.population * 100
                    if pct >= 1:
                        sentences.append(f"Its population of {place.population:,} accounts for {pct:.1f}% of {city.name}.")

            result["breadcrumb"] = [
                {"name": reg.name, "code": reg.psgc_code},
                {"name": prov.name, "code": prov.psgc_code},
                {"name": city.name, "code": city.psgc_code},
                {"name": place.name, "code": place.psgc_code},
            ]
            result["parent_name"] = city.name
            result["urban_rural"] = place.urban_rural
            result["island_group"] = reg.island_group.value if reg.island_group else None
            result["children_count"] = 0

        elif level == "city":
            prov = store.get_province(place.province_code)
            reg = store.get_region(place.region_code)

            kind = "a highly urbanized city" if place.city_class == "Highly Urbanized City" else \
                   "a component city" if place.city_class == "Component City" else \
                   "an independent component city" if place.city_class == "Independent Component City" else \
                   "a municipality" if place.geographic_level == "Mun" else "a city"
            sentences.append(f"{place.name} is {kind} in {reg.name}.")

            bgys = place.children
            if bgys:
                sentences.append(f"It has {len(bgys)} barangays.")

            if place.population:
                sentences.append(f"Its population is {place.population:,} based on the 2024 Census.")

            if place.income_classification:
                sentences.append(f"It is classified as a {place.income_classification} income municipality/city.")

            subs = place.sub_municipalities
            bc = [{"name": reg.name, "code": reg.psgc_code},
                  {"name": prov.name, "code": prov.psgc_code},
                  {"name": place.name, "code": place.psgc_code}]
            if prov.name == reg.name:
                bc = [{"name": reg.name, "code": reg.psgc_code},
                      {"name": place.name, "code": place.psgc_code}]
            result["breadcrumb"] = bc
            result["parent_name"] = prov.name
            result["island_group"] = reg.island_group.value if reg.island_group else None
            result["income_classification"] = place.income_classification
            result["city_class"] = place.city_class
            result["children_count"] = len(bgys)
            if subs:
                result["sub_municipalities"] = [{"name": s.name, "psgc_code": s.psgc_code, "barangay_count": len(s.children)} for s in subs]

        elif level == "province":
            reg = store.get_region(place.region_code)
            cities = store.cities_by_province(place.psgc_code)
            sentences.append(f"{place.name} is a province in {reg.name}.")
            if cities:
                sentences.append(f"It has {len(cities)} cities and municipalities.")
            if place.population:
                sentences.append(f"Its population is {place.population:,}.")
            result["breadcrumb"] = [
                {"name": reg.name, "code": reg.psgc_code},
                {"name": place.name, "code": place.psgc_code},
            ]
            result["parent_name"] = reg.name
            result["island_group"] = reg.island_group.value if reg.island_group else None
            result["income_classification"] = place.income_classification
            result["children_count"] = len(cities)

        elif level == "region":
            ig = place.island_group.value.title() if place.island_group else ""
            sentences.append(f"{place.name} is a region in the {ig} island group of the Philippines.")
            provs = [p for p in store.provinces_by_region(place.psgc_code) if p.psgc_code != place.psgc_code]
            if provs:
                sentences.append(f"It has {len(provs)} provinces.")
            if place.population:
                total_pop = sum(r.population or 0 for r in store.regions)
                pct = place.population / total_pop * 100 if total_pop else 0
                sentences.append(f"Its population of {place.population:,} accounts for {pct:.1f}% of the national total.")
            result["breadcrumb"] = [{"name": place.name, "code": place.psgc_code}]
            result["island_group"] = place.island_group.value if place.island_group else None
            result["children_count"] = len(provs)

        result["description"] = " ".join(sentences)
        return result

    def _api_parse(self, params):
        addr = params.get("q", [""])[0]
        r = psgc.parse_address(addr)
        return r.to_dict()

    def _api_stats(self):
        return {
            "version": psgc.__version__,
            "data_date": psgc.__data_date__,
            "regions": len(psgc.regions),
            "provinces": len(psgc.provinces),
            "cities": len(psgc.cities),
            "barangays": len(psgc.barangays),
        }

    def _api_regions(self):
        return [{"name": r.name, "psgc_code": r.psgc_code,
                 "island_group": r.island_group.value if r.island_group else None,
                 "population": r.population,
                 "latitude": r.coordinate.latitude if r.coordinate else None,
                 "longitude": r.coordinate.longitude if r.coordinate else None}
                for r in psgc.regions]

    def _api_geojson(self, params):
        level = params.get("level", ["barangay"])[0]
        region = params.get("region", [None])[0]
        return psgc.to_geojson(level=level, region=region, as_dict=True)

    def _index_page(self):
        return (Path(__file__).parent / "index.html").read_text()


if __name__ == "__main__":
    import socket

    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else PORT))

    for attempt in range(20):
        try:
            server = http.server.HTTPServer(("", port), DemoHandler)
            break
        except OSError:
            port += 1
    else:
        print("Could not find an open port.")
        sys.exit(1)

    print(f"psgc demo running on http://localhost:{port}")
    print(f"Version: {psgc.__version__} | Data: {psgc.__data_date__}")
    print(f"Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")

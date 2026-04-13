"""Command-line interface for psgc."""

from __future__ import annotations

import click

from psgc.config import PSGC_DATA_DATE, PSGC_VERSION


@click.group()
@click.version_option(version=PSGC_VERSION, prog_name="psgc")
def cli() -> None:
    """Philippine Standard Geographic Code (PSGC) toolkit."""


@cli.command()
@click.argument("query")
@click.option("-n", "--limit", default=5, help="Number of results.")
@click.option("--threshold", default=60.0, help="Minimum match score (0-100).")
@click.option("--phonetic", is_flag=True, help="Apply Filipino phonetic rules.")
@click.option("--hook", multiple=True, help="Match hooks: barangay, city, province, region.")
def search(query: str, limit: int, threshold: float, phonetic: bool, hook: tuple[str, ...]) -> None:
    """Fuzzy search for geographic locations."""
    from psgc.search.fuzzy import search as do_search

    hooks = list(hook) if hook else None
    results = do_search(query, n=limit, threshold=threshold, phonetic=phonetic, match_hooks=hooks)

    if not results:
        click.echo("No matches found.")
        return

    for i, r in enumerate(results, 1):
        click.echo(f"\n{i}. {r.name} (score: {r.score})")
        click.echo(f"   PSGC: {r.psgc_code} | Level: {r.level}")
        place = r.place
        if hasattr(place, "city_code"):
            from psgc._loader import get_store
            store = get_store()
            click.echo(f"   City: {store.get_city(place.city_code).name}")
            click.echo(f"   Province: {store.get_province(place.province_code).name}")
            click.echo(f"   Region: {store.get_region(place.region_code).name}")
        elif hasattr(place, "province_code"):
            from psgc._loader import get_store
            store = get_store()
            click.echo(f"   Province: {store.get_province(place.province_code).name}")
            click.echo(f"   Region: {store.get_region(place.region_code).name}")
        elif hasattr(place, "region_code"):
            from psgc._loader import get_store
            click.echo(f"   Region: {get_store().get_region(place.region_code).name}")
        if place.coordinate:
            click.echo(f"   Coordinates: {place.coordinate.latitude}, {place.coordinate.longitude}")


@cli.command()
@click.argument("prefix")
@click.option("-n", "--limit", default=10, help="Number of suggestions.")
def suggest(prefix: str, limit: int) -> None:
    """Autocomplete suggestions for a prefix."""
    from psgc.search.autocomplete import suggest as do_suggest

    results = do_suggest(prefix, limit=limit)
    if not results:
        click.echo("No suggestions found.")
        return

    for r in results:
        click.echo(f"  {r['name']} ({r['level']})")


@cli.command()
@click.argument("latitude", type=float)
@click.argument("longitude", type=float)
@click.option("-n", "--limit", default=5, help="Number of results.")
def nearest(latitude: float, longitude: float, limit: int) -> None:
    """Find nearest barangays to a GPS coordinate."""
    from psgc.geo.spatial import get_spatial_index

    results = get_spatial_index().nearest(latitude, longitude, n=limit)
    if not results:
        click.echo("No results found.")
        return

    for i, r in enumerate(results, 1):
        click.echo(f"\n{i}. {r.name} ({r.distance_km:.3f} km)")
        click.echo(f"   PSGC: {r.psgc_code}")
        if r.place.coordinate:
            click.echo(f"   Coordinates: {r.place.coordinate.latitude}, {r.place.coordinate.longitude}")


@cli.command("within-radius")
@click.argument("latitude", type=float)
@click.argument("longitude", type=float)
@click.option("--km", default=5.0, help="Radius in kilometers.")
def within_radius(latitude: float, longitude: float, km: float) -> None:
    """Find all barangays within a radius."""
    from psgc.geo.spatial import get_spatial_index

    results = get_spatial_index().within_radius(latitude, longitude, radius_km=km)
    click.echo(f"Found {len(results)} barangay(s) within {km} km:")

    for r in results:
        click.echo(f"  {r.name} - {r.distance_km:.3f} km (PSGC: {r.psgc_code})")


@cli.command("reverse-geocode")
@click.argument("latitude", type=float)
@click.argument("longitude", type=float)
def reverse_geocode_cmd(latitude: float, longitude: float) -> None:
    """Reverse geocode coordinates to a barangay."""
    from psgc.geo.reverse import reverse_geocode

    try:
        result = reverse_geocode(latitude, longitude)
    except LookupError as e:
        click.echo(f"Error: {e}")
        return

    click.echo(f"Barangay: {result.barangay}")
    click.echo(f"City: {result.city}")
    click.echo(f"Province: {result.province}")
    click.echo(f"Region: {result.region}")
    if result.place.zip_code:
        click.echo(f"ZIP Code: {result.place.zip_code}")
    click.echo(f"Distance: {result.distance_km:.3f} km (method: {result.method})")


@cli.command()
@click.argument("place_a")
@click.argument("place_b")
def distance(place_a: str, place_b: str) -> None:
    """Calculate distance between two places."""
    import psgc as _psgc
    from psgc.geo.distance import haversine

    try:
        a = _psgc.get(place_a)
    except LookupError:
        click.echo(f"Could not find: {place_a}")
        return
    try:
        b = _psgc.get(place_b)
    except LookupError:
        click.echo(f"Could not find: {place_b}")
        return

    if a.coordinate is None or b.coordinate is None:
        click.echo("Coordinate data not available for one or both places.")
        return

    dist = haversine(
        a.coordinate.latitude, a.coordinate.longitude,
        b.coordinate.latitude, b.coordinate.longitude,
    )
    click.echo(f"{a.name} <-> {b.name}")
    click.echo(f"Distance: {dist:.3f} km")


@cli.command("parse")
@click.argument("address")
def parse_address_cmd(address: str) -> None:
    """Parse a Filipino address into components."""
    from psgc.address.parser import parse_address

    result = parse_address(address)
    click.echo(f"Raw: {result.raw}")
    if result.street:
        click.echo(f"Street: {result.street}")
    if result.barangay:
        click.echo(f"Barangay: {result.barangay}")
    if result.city:
        click.echo(f"City: {result.city}")
    if result.province:
        click.echo(f"Province: {result.province}")
    if result.region:
        click.echo(f"Region: {result.region}")
    if result.zip_code:
        click.echo(f"ZIP Code: {result.zip_code}")
    if result.confidence > 0:
        click.echo(f"Confidence: {result.confidence:.0%}")


@cli.command()
@click.option("--format", "fmt", type=click.Choice(["geojson", "csv", "json", "yaml"]), default="json")
@click.option("--level", type=click.Choice(["region", "province", "city", "barangay"]), default="barangay")
@click.option("--region", default=None, help="Filter by region name.")
@click.option("--province", default=None, help="Filter by province name.")
@click.option("--island-group", default=None, help="Filter by island group (luzon/visayas/mindanao).")
@click.option("-o", "--output", default=None, help="Output file path.")
def export(fmt: str, level: str, region: str | None, province: str | None, island_group: str | None, output: str | None) -> None:
    """Export geographic data in various formats."""
    if fmt == "geojson":
        from psgc.export.geojson import to_geojson
        result = to_geojson(level=level, region=region, province=province, output=output)
    elif fmt == "csv":
        from psgc.export.formats import to_csv
        result = to_csv(level=level, region=region, province=province, island_group=island_group, output=output)
    elif fmt == "yaml":
        from psgc.export.formats import to_yaml
        result = to_yaml(level=level, region=region, province=province, island_group=island_group, output=output)
    else:
        from psgc.export.formats import to_json
        result = to_json(level=level, region=region, province=province, island_group=island_group, output=output)

    if output:
        click.echo(f"Exported to {result}")
    else:
        click.echo(result)


@cli.group()
def info() -> None:
    """Show package and data information."""


@info.command()
def version() -> None:
    """Show package version and data date."""
    click.echo(f"psgc {PSGC_VERSION}")
    click.echo(f"Data: PSGC {PSGC_DATA_DATE}")


@info.command()
def stats() -> None:
    """Show data statistics."""
    from psgc._loader import get_store

    store = get_store()
    click.echo(f"psgc {PSGC_VERSION} (PSGC {PSGC_DATA_DATE})")
    click.echo(f"  Regions:    {len(store.regions):>6}")
    click.echo(f"  Provinces:  {len(store.provinces):>6}")
    click.echo(f"  Cities:     {len(store.cities):>6}")
    click.echo(f"  Barangays:  {len(store.barangays):>6}")
    click.echo(f"  ZIP Codes:  {len(store.zip_codes):>6}")

    total_pop = sum(r.population or 0 for r in store.regions)
    click.echo(f"  Population: {total_pop:>6,}")


@cli.command()
@click.argument("code")
def validate(code: str) -> None:
    """Validate a PSGC code."""
    from psgc.address.validator import validate as do_validate

    is_valid, reason = do_validate(code)
    if is_valid:
        click.secho(f"Valid: {reason}", fg="green")
    else:
        click.secho(f"Invalid: {reason}", fg="red")


@cli.command("zip")
@click.argument("zip_code")
def zip_lookup(zip_code: str) -> None:
    """Look up a ZIP code."""
    from psgc._loader import get_store

    result = get_store().lookup_zip(zip_code)
    if result is None:
        click.echo(f"ZIP code {zip_code} not found.")
        return

    click.echo(f"ZIP Code: {zip_code}")
    click.echo(f"Area: {result.get('area', 'N/A')}")
    click.echo(f"City: {result.get('city', 'N/A')}")
    click.echo(f"Province: {result.get('province', 'N/A')}")


if __name__ == "__main__":
    cli()

# Copyright (c) 2018 The Harmonica Developers.
# Distributed under the terms of the BSD 3-Clause License.
# SPDX-License-Identifier: BSD-3-Clause
#
# This code is part of the Fatiando a Terra project (https://www.fatiando.org)
#
"""
Test forward modelling for point masses.
"""
import os
import warnings
from pathlib import Path

import numpy as np
import numpy.testing as npt
import pytest
import verde as vd

from ..constants import GRAVITATIONAL_CONST
from ..forward.point import point_gravity, point_mass_gravity
from ..forward.utils import distance_cartesian
from .utils import run_only_with_numba

MODULE_DIR = Path(os.path.dirname(__file__))
TEST_DATA_DIR = MODULE_DIR / "data"


def test_invalid_coordinate_system():
    "Check if invalid coordinate system is passed"
    coordinates = [0.0, 0.0, 0.0]
    point_mass = [0.0, 0.0, 0.0]
    mass = 1.0
    with pytest.raises(ValueError):
        point_gravity(
            coordinates,
            point_mass,
            mass,
            "potential",
            "this-is-not-a-valid-coordinate-system",
        )


def test_not_implemented_field():
    """
    Check if NotImplementedError is raised after asking a non-implemented field
    """
    coordinates = [0.0, 0.0, 0.0]
    point_mass = [0.0, 0.0, 0.0]
    mass = 1.0
    coordinate_system = "spherical"
    for field in ("g_northing", "g_easting"):
        with pytest.raises(NotImplementedError):
            point_gravity(
                coordinates,
                point_mass,
                mass,
                field,
                coordinate_system,
            )


def test_invalid_field():
    "Check if an invalid gravitational field is passed as argument"
    coordinates = [0.0, 0.0, 0.0]
    point_mass = [0.0, 0.0, 0.0]
    mass = 1.0
    for coordinate_system in ("spherical", "cartesian"):
        with pytest.raises(ValueError):
            point_gravity(
                coordinates,
                point_mass,
                mass,
                "this-field-does-not-exist",
                coordinate_system,
            )


def test_invalid_masses_array():
    "Check if error is raised when masses shape does not match points shape"
    # Create a set of 3 point masses
    points = [[-10, 0, 10], [-10, 0, 10], [-100, 0, 100]]
    # Generate a two element masses
    masses = [1000, 2000]
    coordinates = [0, 0, 250]
    with pytest.raises(ValueError):
        point_gravity(
            coordinates,
            points,
            masses,
            field="potential",
            coordinate_system="cartesian",
        )


# ---------------------------
# Cartesian coordinates tests
# ---------------------------


@pytest.fixture(name="point_mass")
def fixture_point_mass():
    """
    Defines a point located in the origin with a mass of 500kg
    """
    point = [0, 0, 0]
    mass = [5000]
    return point, mass


@pytest.fixture(name="sample_coordinates_potential")
def fixture_sample_coordinates_potential():
    """
    Define a sample computation points and the gravity potential field
    generated by the point_mass.
    """
    sample_data_file = TEST_DATA_DIR / "sample_point_gravity.csv"
    easting, northing, upward, potential = np.loadtxt(
        sample_data_file, delimiter=",", unpack=True
    )
    return (easting, northing, upward, potential)


@pytest.mark.use_numba
def test_potential_cartesian_known_values(point_mass, sample_coordinates_potential):
    """
    Compare the computed gravitational potential with reference values
    """
    point, mass = point_mass[:]
    coordinates = sample_coordinates_potential[:3]
    precomputed_potential = sample_coordinates_potential[-1]
    # Compute potential gravity field on each computation point
    results = point_gravity(coordinates, point, mass, "potential", "cartesian")
    npt.assert_allclose(results, precomputed_potential)


@pytest.mark.use_numba
def test_point_mass_gravity_deprecated(point_mass, sample_coordinates_potential):
    """
    Test the soon-to-be-deprecated point_mass_gravity function
    """
    point, mass = point_mass[:]
    coordinates = sample_coordinates_potential[:3]
    precomputed_potential = sample_coordinates_potential[-1]
    # Check if a FutureWarning is raised
    with warnings.catch_warnings(record=True) as warn:
        results = point_mass_gravity(coordinates, point, mass, "potential", "cartesian")
        assert len(warn) == 1
        assert issubclass(warn[-1].category, FutureWarning)
    npt.assert_allclose(results, precomputed_potential)


@pytest.mark.use_numba
def test_potential_cartesian_symmetry():
    """
    Test if potential field of a point mass has symmetry in Cartesian coords
    """
    # Define a single point mass
    point_mass = [1.1, 1.2, 1.3]
    masses = [2670]
    # Define a set of computation points at a fixed distance from the point
    # mass
    distance = 3.3
    easting = point_mass[0] * np.ones(6)
    northing = point_mass[1] * np.ones(6)
    upward = point_mass[2] * np.ones(6)
    easting[0] += distance
    easting[1] -= distance
    northing[2] += distance
    northing[3] -= distance
    upward[4] += distance
    upward[5] -= distance
    coordinates = [easting, northing, upward]
    # Compute potential gravity field on each computation point
    results = point_gravity(coordinates, point_mass, masses, "potential", "cartesian")
    npt.assert_allclose(*results)


@pytest.mark.use_numba
def test_g_z_symmetry():
    """
    Test if g_z field of a point mass has symmetry in Cartesian coordinates
    """
    # Define a single point mass
    point_mass = [1.1, 1.2, 1.3]
    masses = [2670]
    # Define a pair of computation points above and below the point mass
    distance = 3.3
    easting = point_mass[0] * np.ones(2)
    northing = point_mass[1] * np.ones(2)
    upward = point_mass[2] * np.ones(2)
    upward[0] += distance
    upward[1] -= distance
    coordinates = [easting, northing, upward]
    # Compute g_z gravity field on each computation point
    results = point_gravity(coordinates, point_mass, masses, "g_z", "cartesian")
    npt.assert_allclose(results[0], -results[1])


@pytest.mark.use_numba
def test_g_z_relative_error():
    """
    Test the relative error in computing the g_z component
    """
    # Define a single point mass
    point_mass = (1, -67, -300.7)
    mass = 250
    coordinates_p = (0, -39, -13)
    # Compute the z component
    exact_deriv = point_gravity(coordinates_p, point_mass, mass, "g_z", "cartesian")
    # Compute the numerical derivative of potential
    delta = 0.1
    easting = np.zeros(2) + coordinates_p[0]
    northing = np.zeros(2) + coordinates_p[1]
    upward = np.array([coordinates_p[2] - delta, coordinates_p[2] + delta])
    coordinates = (easting, northing, upward)
    potential = point_gravity(coordinates, point_mass, mass, "potential", "cartesian")
    # Remember that the ``g_z`` field returns the downward component of the
    # gravitational acceleration. As a consequence, the numerical
    # derivativative is multiplied by -1.
    approximated_deriv = -1e5 * (potential[1] - potential[0]) / (2.0 * delta)

    # Compute the relative error
    relative_error = np.abs((approximated_deriv - exact_deriv) / exact_deriv)

    # Bound value
    distance = distance_cartesian(coordinates_p, point_mass)
    bound_value = 1.5 * (delta / distance) ** 2

    # Compare the results
    npt.assert_array_less(relative_error, bound_value)


@pytest.mark.use_numba
def test_g_z_sign():
    """
    Test if g_z field of a positive point mass has the correct sign
    """
    # Define a single point mass
    point_mass = [-10, 100.2, -300.7]
    mass = [2670]
    # Define three computation points located above, at the same depth and
    # below the point mass
    easting = np.zeros(3)
    northing = np.zeros(3) + 52.3
    upward = np.array([100.11, -300.7, -400])
    coordinates = [easting, northing, upward]
    # Compute g_z gravity field on each computation point
    results = point_gravity(coordinates, point_mass, mass, "g_z", "cartesian")
    assert np.sign(mass) == np.sign(results[0])
    npt.assert_allclose(results[1], 0)
    assert np.sign(mass) == -np.sign(results[2])


@pytest.mark.use_numba
def test_g_northing_symmetry():
    """
    Test if g_northing field of a point mass has symmetry in Cartesian
    coordinates
    """
    # Define a single point mass
    point_mass = [-7.9, 25, -130]
    masses = [2670]
    # Define a pair of computation points northward and southward the point
    # mass
    distance = 6.1
    easting = point_mass[0] + np.zeros(2)
    northing = point_mass[1] + np.zeros(2)
    upward = point_mass[2] + np.zeros(2)
    northing[0] += distance
    northing[1] -= distance
    coordinates = [easting, northing, upward]
    # Compute g_northing gravity field on each computation point
    results = point_gravity(coordinates, point_mass, masses, "g_northing", "cartesian")
    npt.assert_allclose(results[0], -results[1])


@pytest.mark.use_numba
def test_g_northing_relative_error():
    """
    Test the relative error in computing the g_northing component
    """
    # Define a single point mass
    point_mass = (1, -67, -300.7)
    mass = 250
    coordinates_p = (0, -39, -13)
    # Compute the northing component
    exact_deriv = point_gravity(
        coordinates_p, point_mass, mass, "g_northing", "cartesian"
    )
    # Compute the numerical derivative of potential
    delta = 0.1
    easting = np.zeros(2) + coordinates_p[0]
    northing = np.array([coordinates_p[1] - delta, coordinates_p[1] + delta])
    upward = np.zeros(2) + coordinates_p[2]
    coordinates = (easting, northing, upward)
    potential = point_gravity(coordinates, point_mass, mass, "potential", "cartesian")
    approximated_deriv = 1e5 * (potential[1] - potential[0]) / (2.0 * delta)

    # Compute the relative error
    relative_error = np.abs((approximated_deriv - exact_deriv) / exact_deriv)

    # Bound value
    distance = distance_cartesian(coordinates_p, point_mass)
    bound_value = 1.5 * (delta / distance) ** 2

    # Compare the results
    npt.assert_array_less(relative_error, bound_value)


@pytest.mark.use_numba
def test_g_northing_sign():
    """
    Test if g_northing field of a positive point mass has the correct sign
    """
    # Define a single point mass
    point_mass = [-10, 100.2, -300.7]
    mass = [2670]
    # Define three computation points located above the point mass, along the
    # north axis
    easting = np.zeros(3)
    northing = np.array([0, 100.2, 210.7])
    upward = np.zeros(3)
    coordinates = [easting, northing, upward]
    # Compute g_northing gravity field on each computation point
    results = point_gravity(coordinates, point_mass, mass, "g_northing", "cartesian")
    assert np.sign(mass) == np.sign(results[0])
    npt.assert_allclose(results[1], 0)
    assert np.sign(mass) == -np.sign(results[2])


@pytest.mark.use_numba
def test_g_easting_symmetry():
    """
    Test if g_easting field of a point mass has symmetry in Cartesian
    coordinates
    """
    # Define a single point mass
    point_mass = [191, -5, 0]
    masses = [2670]
    # Define a pair of computation points northward and southward the point
    # mass
    distance = 4.6
    easting = point_mass[0] + np.zeros(2)
    northing = point_mass[1] + np.zeros(2)
    upward = point_mass[2] + np.zeros(2)
    easting[0] += distance
    easting[1] -= distance
    coordinates = [easting, northing, upward]
    # Compute g_easting gravity field on each computation point
    results = point_gravity(coordinates, point_mass, masses, "g_easting", "cartesian")
    npt.assert_allclose(results[0], -results[1])


@pytest.mark.use_numba
def test_g_easting_relative_error():
    """
    Test the relative error in computing the g_easting component
    """
    # Define a single point mass
    point_mass = (20, 54, -500.7)
    mass = 200
    coordinates_p = (-3, 24, -10)
    # Compute the easting component
    exact_deriv = point_gravity(
        coordinates_p, point_mass, mass, "g_easting", "cartesian"
    )
    # Compute the numerical derivative of potential
    delta = 0.1
    easting = np.array([coordinates_p[0] - delta, coordinates_p[0] + delta])
    northing = np.zeros(2) + coordinates_p[1]
    upward = np.zeros(2) + coordinates_p[2]
    coordinates = (easting, northing, upward)
    potential = point_gravity(coordinates, point_mass, mass, "potential", "cartesian")
    approximated_deriv = 1e5 * (potential[1] - potential[0]) / (2.0 * delta)

    # Compute the relative error
    relative_error = np.abs((approximated_deriv - exact_deriv) / exact_deriv)

    # Bound value
    distance = distance_cartesian(coordinates_p, point_mass)
    bound_value = 1.5 * (delta / distance) ** 2

    # Compare the results
    npt.assert_array_less(relative_error, bound_value)


@pytest.mark.use_numba
def test_g_easting_sign():
    """
    Test if g_easting field of a positive point mass has the correct sign
    """
    # Define a single point mass
    point_mass = [-10, 100.2, -300.7]
    mass = [2670]
    # Define three computation points located above the point mass, along the
    # east axis
    easting = np.array([-150.7, -10, 79])
    northing = np.zeros(3)
    upward = np.zeros(3)
    coordinates = [easting, northing, upward]
    # Compute g_easting gravity field on each computation point
    results = point_gravity(coordinates, point_mass, mass, "g_easting", "cartesian")
    assert np.sign(mass) == np.sign(results[0])
    npt.assert_allclose(results[1], 0)
    assert np.sign(mass) == -np.sign(results[2])


@run_only_with_numba
def test_point_mass_cartesian_parallel():
    """
    Check if parallel and serial runs return the same result
    """
    region = (2e3, 10e3, -3e3, 5e3)
    points = vd.scatter_points(region, size=30, extra_coords=-1e3, random_state=0)
    masses = np.arange(points[0].size)
    coordinates = vd.grid_coordinates(region=region, spacing=1e3, extra_coords=0)
    for field in ("potential", "g_z", "g_northing", "g_easting"):
        result_serial = point_gravity(
            coordinates, points, masses, field=field, parallel=False
        )
        result_parallel = point_gravity(
            coordinates, points, masses, field=field, parallel=True
        )
        npt.assert_allclose(result_serial, result_parallel)


# ---------------------------
# Spherical coordinates tests
# ---------------------------
@pytest.mark.use_numba
def test_point_mass_on_origin():
    "Check potential and g_z of point mass on origin in spherical coordinates"
    point_mass = [0.0, 0.0, 0.0]
    mass = 2.0
    radius = np.logspace(1, 8, 5)
    longitude = np.linspace(-180, 180, 37)
    latitude = np.linspace(-90, 90, 19)
    longitude, latitude, radius = np.meshgrid(longitude, latitude, radius)
    # Analytical solutions (accelerations are in mgal and tensor components in
    # eotvos)
    analytical = {
        "potential": GRAVITATIONAL_CONST * mass / radius,
        "g_z": GRAVITATIONAL_CONST * mass / radius ** 2 * 1e5,
    }
    # Compare results with analytical solutions
    for field, solution in analytical.items():
        npt.assert_allclose(
            point_gravity(
                [longitude, latitude, radius], point_mass, mass, field, "spherical"
            ),
            solution,
        )


@pytest.mark.use_numba
def test_point_mass_same_radial_direction():
    """
    Check potential and g_z of point mass and computation point on same radius
    """
    sphere_radius = 3.0
    mass = 2.0
    for longitude in np.linspace(-180, 180, 37):
        for latitude in np.linspace(-90, 90, 19):
            for height in np.logspace(0, 4, 5):
                point_mass = [longitude, latitude, sphere_radius]
                coordinates = [
                    np.array(longitude),
                    np.array(latitude),
                    np.array(height + sphere_radius),
                ]
                # Analytical solutions
                # (accelerations are in mgal and tensor components in eotvos)
                analytical = {
                    "potential": GRAVITATIONAL_CONST * mass / height,
                    "g_z": GRAVITATIONAL_CONST * mass / height ** 2 * 1e5,
                }
                # Compare results with analytical solutions
                for field, solution in analytical.items():
                    npt.assert_allclose(
                        point_gravity(
                            coordinates, point_mass, mass, field, "spherical"
                        ),
                        solution,
                    )


@pytest.mark.use_numba
def test_point_mass_potential_on_equator():
    "Check potential field on equator and same radial coordinate"
    radius = 3.0
    mass = 2.0
    latitude = 0.0
    for longitude_p in np.linspace(0, 350, 36):
        point_mass = [longitude_p, latitude, radius]
        for longitude in np.linspace(0, 350, 36):
            if longitude != longitude_p:
                coordinates = [
                    np.array(longitude),
                    np.array(latitude),
                    np.array(radius),
                ]
                # Analytical solutions
                # (accelerations are in mgal and tensor components in eotvos)
                distance = (
                    2 * radius * np.sin(0.5 * np.radians(abs(longitude - longitude_p)))
                )
                analytical = {"potential": GRAVITATIONAL_CONST * mass / distance}
                # Compare results with analytical solutions
                npt.assert_allclose(
                    point_gravity(
                        coordinates, point_mass, mass, "potential", "spherical"
                    ),
                    analytical["potential"],
                )


@pytest.mark.use_numba
def test_point_mass_potential_on_same_meridian():
    "Check potential field on same meridian and radial coordinate"
    radius = 3.0
    mass = 2.0
    longitude = 0.0
    for latitude_p in np.linspace(-90, 90, 19):
        point_mass = [longitude, latitude_p, radius]
        for latitude in np.linspace(-90, 90, 19):
            if latitude != latitude_p:
                coordinates = [
                    np.array(longitude),
                    np.array(latitude),
                    np.array(radius),
                ]
                # Analytical solutions
                # (accelerations are in mgal and tensor components in eotvos)
                distance = (
                    2 * radius * np.sin(0.5 * np.radians(abs(latitude - latitude_p)))
                )
                analytical = {"potential": GRAVITATIONAL_CONST * mass / distance}
                # Compare results with analytical solutions
                npt.assert_allclose(
                    point_gravity(
                        coordinates, point_mass, mass, "potential", "spherical"
                    ),
                    analytical["potential"],
                )


@run_only_with_numba
def test_point_mass_spherical_parallel():
    """
    Check if parallel and serial runs return the same result
    """
    region = (2, 10, -3, 5)
    radius = 6400e3
    points = vd.scatter_points(
        region, size=30, extra_coords=radius - 10e3, random_state=0
    )
    masses = np.arange(points[0].size)
    coordinates = vd.grid_coordinates(region=region, spacing=1, extra_coords=radius)
    for field in ("potential", "g_z"):
        result_serial = point_gravity(
            coordinates,
            points,
            masses,
            field=field,
            coordinate_system="spherical",
            parallel=False,
        )
        result_parallel = point_gravity(
            coordinates,
            points,
            masses,
            field=field,
            coordinate_system="spherical",
            parallel=True,
        )
        npt.assert_allclose(result_serial, result_parallel)

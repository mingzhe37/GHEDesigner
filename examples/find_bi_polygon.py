# Purpose: Design a bi-uniform constrained polygonal field using the common
# design interface with a single U-tube, multiple U-tube and coaxial tube
# borehole heat exchanger.

# This search is described in section 4.4.5 from pages 146-148 in Cook (2021).

import csv
import tempfile
from pathlib import Path
from sys import path
from time import time as clock

import pandas as pd
import pygfunction as gt

# use the ghedt import as a flag for determining whether we need to add to path
try:
    import ghedt  # noqa: F401
except ImportError:
    # we are probably in VSCode or some other development setup
    # just add the root of the repo to path just like it will be in deployment
    root_dir = Path(__file__).parent.parent.resolve()
    path.insert(0, str(root_dir))

import ghedt as dt
import ghedt.design as design
import ghedt.geometry as media
import ghedt.peak_load_analysis_tool as plat
from ghedt.output import OutputDesignDetails


def main():

    # This file contains three examples utilizing the bi-uniform polygonal design algorithm for a single U, double U, and
    # coaxial tube design. The results from these examples are exported to the "DesignExampleOutput" folder.

    # Single U-tube Example

    # Output File Configuration
    projectName = "Atlanta Office Building: Design Example"
    note = "Bi-Uniform Polygon Usage Example: Single U Tube"
    author = "Jane Doe"
    IterationName = "Example 6"
    outputFileDirectory = tempfile.mkdtemp()

    # Borehole dimensions
    H = 96.0  # Borehole length (m)
    D = 2.0  # Borehole buried depth (m)
    r_b = 0.075  # Borehole radius (m)
    # B = 5.0  # Borehole spacing (m)

    # Single and Multiple U-tube Pipe Dimensions
    r_out = 26.67 / 1000.0 / 2.0  # Pipe outer radius (m)
    r_in = 21.6 / 1000.0 / 2.0  # Pipe inner radius (m)
    s = 32.3 / 1000.0  # Inner-tube to inner-tube Shank spacing (m)
    epsilon = 1.0e-6  # Pipe roughness (m)

    # Single U Tube Pipe Positions
    pos_single = plat.media.Pipe.place_pipes(s, r_out, 1)
    single_u_tube = plat.borehole_heat_exchangers.SingleUTube

    # Thermal conductivities
    k_p = 0.4  # Pipe thermal conductivity (W/m.K)
    k_s = 2.0  # Ground thermal conductivity (W/m.K)
    k_g = 1.0  # Grout thermal conductivity (W/m.K)

    # Volumetric heat capacities
    rhoCp_p = 1542.0 * 1000.0  # Pipe volumetric heat capacity (J/K.m3)
    rhoCp_s = 2343.493 * 1000.0  # Soil volumetric heat capacity (J/K.m3)
    rhoCp_g = 3901.0 * 1000.0  # Grout volumetric heat capacity (J/K.m3)

    # Instantiating Pipe
    pipe_single = plat.media.Pipe(pos_single, r_in, r_out, s, epsilon, k_p, rhoCp_p)

    # Instantiating Soil Properties
    ugt = 18.3  # Undisturbed ground temperature (degrees Celsius)
    soil = plat.media.Soil(k_s, rhoCp_s, ugt)

    # Instantiating Grout Properties
    grout = plat.media.Grout(k_g, rhoCp_g)

    # Fluid properties
    fluid = gt.media.Fluid(fluid_str="Water", percent=0.0)

    # Fluid Flow Properties
    V_flow = 0.2  # Volumetric flow rate (L/s)
    # Note: The flow parameter can be borehole or system.
    flow = "borehole"

    # Instantiate a Borehole
    borehole = gt.boreholes.Borehole(H, D, r_b, x=0.0, y=0.0)

    # Simulation parameters
    start_month = 1
    n_years = 20
    end_month = n_years * 12
    max_EFT_allowable = 35  # degrees Celsius (HPEFT)
    min_EFT_allowable = 5  # degrees Celsius (HPEFT)
    max_Height = 135.0  # in meters
    min_Height = 60  # in meters
    sim_params = plat.media.SimulationParameters(
        start_month,
        end_month,
        max_EFT_allowable,
        min_EFT_allowable,
        max_Height,
        min_Height,
    )

    # Process loads from file
    # read in the csv file and convert the loads to a list of length 8760
    hourly_extraction: dict = pd.read_csv(Path(__file__).parent / "data" / "Atlanta_Office_Building_Loads.csv").to_dict("list")
    # Take only the first column in the dictionary
    hourly_extraction_ground_loads: list = hourly_extraction[
        list(hourly_extraction.keys())[0]
    ]

    # Polygonal design constraints are the land and range of B-spacing
    B_min = 5  # in m
    B_max_x = 25  # in m
    B_max_y = B_max_x  # in m

    # Building Description
    propertyBoundaryFile = Path(__file__).parent / "data" / "PropBound.csv"
    NogoZoneFile = Path(__file__).parent / "data" / "NogoZone1.csv"

    propA = []  # in meters
    ngA = []  # in meters

    with open(propertyBoundaryFile, "r", newline="") as pF:
        cR = csv.reader(pF)
        for line in cR:
            L = []
            for row in line:
                L.append(float(row))
            propA.append(L)

    with open(NogoZoneFile, "r", newline="") as ngF:
        cR = csv.reader(ngF)
        ngA.append([])
        for line in cR:
            L = []
            for row in line:
                L.append(float(row))
            ngA[-1].append(L)

    """ Geometric constraints for the `bi-rectangle_constrained` routine:
      - B_min
      - B_max_x
      - B_max_y
    """
    geometric_constraints = media.GeometricConstraints(
        B_min=B_min, B_max_y=B_max_y, B_max_x=B_max_x
    )

    # Single U-tube
    # -------------
    design_single_u_tube = design.Design(
        V_flow,
        borehole,
        single_u_tube,
        fluid,
        pipe_single,
        grout,
        soil,
        sim_params,
        geometric_constraints,
        hourly_extraction_ground_loads,
        method="hybrid",
        flow=flow,
        routine="bi-rectangle_constrained",
        property_boundary=propA,
        buildingDescriptions=ngA,
    )

    # Find the near-square design for a single U-tube and size it.
    tic = clock()  # Clock Start Time
    bisection_search = design_single_u_tube.find_design(disp=True)  # Finding GHE Design
    bisection_search.ghe.compute_g_functions()  # Calculating Gfunctions for Chosen Design
    bisection_search.ghe.size(
        method="hybrid"
    )  # Calculating the Final Height for the Chosen Design
    toc = clock()  # Clock Stop Time

    # Print Summary of Findings
    subtitle = "* Single U-tube"  # Subtitle for the printed summary
    print(subtitle + "\n" + len(subtitle) * "-")
    print("Calculation time: {0:.2f} seconds".format(toc - tic))
    print("Height: {0:.4f} meters".format(bisection_search.ghe.bhe.b.H))
    nbh = len(bisection_search.ghe.GFunction.bore_locations)
    print("Number of boreholes: {}".format(nbh))
    print("Total Drilling: {0:.1f} meters\n".format(bisection_search.ghe.bhe.b.H * nbh))

    # Generating Ouptut File
    OutputDesignDetails(
        bisection_search,
        toc - tic,
        projectName,
        note,
        author,
        IterationName,
        outputDirectory=outputFileDirectory,
        summaryFile="SummaryOfResults_SU.txt",
        csvF1="TimeDependentValues_SU.csv",
        csvF2="BorefieldData_SU.csv",
        csvF3="Loadings_SU.csv",
        csvF4="GFunction_SU.csv",
    )

    # *************************************************************************************************************
    # Double U-tube Example

    note = "Bi-Uniform Polygon Usage Example: Double U Tube"

    # Double U-tube
    pos_double = plat.media.Pipe.place_pipes(s, r_out, 2)
    double_u_tube = plat.borehole_heat_exchangers.MultipleUTube
    pipe_double = plat.media.Pipe(pos_double, r_in, r_out, s, epsilon, k_p, rhoCp_p)

    # Double U-tube
    # -------------
    design_double_u_tube = dt.design.Design(
        V_flow,
        borehole,
        double_u_tube,
        fluid,
        pipe_double,
        grout,
        soil,
        sim_params,
        geometric_constraints,
        hourly_extraction_ground_loads,
        method="hybrid",
        flow=flow,
        routine="bi-rectangle_constrained",
        property_boundary=propA,
        buildingDescriptions=ngA,
    )

    # Find the near-square design for a single U-tube and size it.
    tic = clock()  # Clock Start Time
    bisection_search = design_double_u_tube.find_design(disp=True)  # Finding GHE Design
    bisection_search.ghe.compute_g_functions()  # Calculating Gfunctions for Chosen Design
    bisection_search.ghe.size(
        method="hybrid"
    )  # Calculating the Final Height for the Chosen Design
    toc = clock()  # Clock Stop Time

    # Print Summary of Findings
    subtitle = "* Double U-tube"  # Subtitle for the printed summary
    print(subtitle + "\n" + len(subtitle) * "-")
    print("Calculation time: {0:.2f} seconds".format(toc - tic))
    print("Height: {0:.4f} meters".format(bisection_search.ghe.bhe.b.H))
    nbh = len(bisection_search.ghe.GFunction.bore_locations)
    print("Number of boreholes: {}".format(nbh))
    print("Total Drilling: {0:.1f} meters\n".format(bisection_search.ghe.bhe.b.H * nbh))

    # Generating Ouptut File
    OutputDesignDetails(
        bisection_search,
        toc - tic,
        projectName,
        note,
        author,
        IterationName,
        outputDirectory=outputFileDirectory,
        summaryFile="SummaryOfResults_DU.txt",
        csvF1="TimeDependentValues_DU.csv",
        csvF2="BorefieldData_DU.csv",
        csvF3="Loadings_DU.csv",
        csvF4="GFunction_DU.csv",
    )

    # *************************************************************************************************************
    # Coaxial Tube Example

    note = "Bi-Uniform Polygon Usage Example: Coaxial Tube"

    # Coaxial tube
    r_in_in = 44.2 / 1000.0 / 2.0
    r_in_out = 50.0 / 1000.0 / 2.0
    # Outer pipe radii
    r_out_in = 97.4 / 1000.0 / 2.0
    r_out_out = 110.0 / 1000.0 / 2.0
    # Pipe radii
    # Note: This convention is different from pygfunction
    r_inner = [r_in_in, r_in_out]  # The radii of the inner pipe from in to out
    r_outer = [r_out_in, r_out_out]  # The radii of the outer pipe from in to out

    k_p_coax = [0.4, 0.4]  # Pipes thermal conductivity (W/m.K)

    # Coaxial tube
    pos_coaxial = (0, 0)
    coaxial_tube = plat.borehole_heat_exchangers.CoaxialPipe
    pipe_coaxial = plat.media.Pipe(
        pos_coaxial, r_inner, r_outer, 0, epsilon, k_p_coax, rhoCp_p
    )

    # Coaxial Tube
    # -------------
    design_coax_tube = dt.design.Design(
        V_flow,
        borehole,
        coaxial_tube,
        fluid,
        pipe_coaxial,
        grout,
        soil,
        sim_params,
        geometric_constraints,
        hourly_extraction_ground_loads,
        method="hybrid",
        flow=flow,
        routine="bi-rectangle_constrained",
        property_boundary=propA,
        buildingDescriptions=ngA,
    )

    # Find the near-square design for a single U-tube and size it.
    tic = clock()  # Clock Start Time
    bisection_search = design_coax_tube.find_design(disp=True)  # Finding GHE Design
    bisection_search.ghe.compute_g_functions()  # Calculating Gfunctions for Chosen Design
    bisection_search.ghe.size(
        method="hybrid"
    )  # Calculating the Final Height for the Chosen Design
    toc = clock()  # Clock Stop Time

    # Print Summary of Findings
    subtitle = "* Coaxial Tube"  # Subtitle for the printed summary
    print(subtitle + "\n" + len(subtitle) * "-")
    print("Calculation time: {0:.2f} seconds".format(toc - tic))
    print("Height: {0:.4f} meters".format(bisection_search.ghe.bhe.b.H))
    nbh = len(bisection_search.ghe.GFunction.bore_locations)
    print("Number of boreholes: {}".format(nbh))
    print("Total Drilling: {0:.1f} meters\n".format(bisection_search.ghe.bhe.b.H * nbh))

    # Generating Ouptut File
    OutputDesignDetails(
        bisection_search,
        toc - tic,
        projectName,
        note,
        author,
        IterationName,
        outputDirectory=outputFileDirectory,
        summaryFile="SummaryOfResults_C.txt",
        csvF1="TimeDependentValues_C.csv",
        csvF2="BorefieldData_C.csv",
        csvF3="Loadings_C.csv",
        csvF4="GFunction_C.csv",
    )


if __name__ == "__main__":
    main()
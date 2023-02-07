# Purpose: Design a square or near-square field using the common design
# interface with a single U-tube, multiple U-tube and coaxial tube.

# This search is described in section 4.3.2 of Cook (2021) from pages 123-129.

from time import time as clock

from ghedesigner.borehole import GHEBorehole
from ghedesigner.borehole_heat_exchangers import SingleUTube, MultipleUTube, CoaxialPipe
from ghedesigner.design import DesignNearSquare
from ghedesigner.geometry import GeometricConstraintsNearSquare
from ghedesigner.media import Pipe, Soil, Grout, GHEFluid
from ghedesigner.simulation import SimulationParameters
from ghedesigner.output import write_output_files
from ghedesigner.tests.ghe_base_case import GHEBaseTest
from ghedesigner.utilities import DesignMethodTimeStep, length_of_side


class TestFindNearSquareMultiyearDesign(GHEBaseTest):

    def test_multiyear_loading(self):
        # This file contains three examples utilizing the square-near-square design algorithm
        # (utilizing a multi-year loading) for a single U, double U, and coaxial tube  The
        # results from these examples are exported to the "DesignExampleOutput" folder.

        # Single U-tube Example

        # Output File Configuration
        project_name = "Atlanta Office Building: Design Example"
        note = "Square-Near-Square w/ Multi-year Loading Usage Example: Single U Tube"
        author = "Jane Doe"
        iteration_name = "Example 2"
        output_file_directory = self.test_outputs_directory / "DesignExampleOutput"

        # Borehole dimensions
        h = 96.0  # Borehole length (m)
        d = 2.0  # Borehole buried depth (m)
        r_b = 0.075  # Borehole radius (m)
        b = 5.0  # Borehole spacing (m)

        # Single and Multiple U-tube Pipe Dimensions
        r_out = 26.67 / 1000.0 / 2.0  # Pipe outer radius (m)
        r_in = 21.6 / 1000.0 / 2.0  # Pipe inner radius (m)
        s = 32.3 / 1000.0  # Inner-tube to inner-tube Shank spacing (m)
        epsilon = 1.0e-6  # Pipe roughness (m)

        # Single U Tube Pipe Positions
        pos_single = Pipe.place_pipes(s, r_out, 1)
        single_u_tube = SingleUTube

        # Thermal conductivities
        k_p = 0.4  # Pipe thermal conductivity (W/m.K)
        k_s = 2.0  # Ground thermal conductivity (W/m.K)
        k_g = 1.0  # Grout thermal conductivity (W/m.K)

        # Volumetric heat capacities
        rho_cp_p = 1542.0 * 1000.0  # Pipe volumetric heat capacity (J/K.m3)
        rho_cp_s = 2343.493 * 1000.0  # Soil volumetric heat capacity (J/K.m3)
        rho_cp_g = 3901.0 * 1000.0  # Grout volumetric heat capacity (J/K.m3)

        # Instantiating Pipe
        pipe_single = Pipe(pos_single, r_in, r_out, s, epsilon, k_p, rho_cp_p)

        # Instantiating Soil Properties
        ugt = 18.3  # Undisturbed ground temperature (degrees Celsius)
        soil = Soil(k_s, rho_cp_s, ugt)

        # Instantiating Grout Properties
        grout = Grout(k_g, rho_cp_g)

        # Fluid properties
        fluid = GHEFluid(fluid_str="Water", percent=0.0)

        # Fluid Flow Properties
        v_flow = 0.2  # Volumetric flow rate (L/s)
        # Note: The flow parameter can be borehole or system.
        flow = "borehole"

        # Instantiate a Borehole
        borehole = GHEBorehole(h, d, r_b, x=0.0, y=0.0)

        # Simulation parameters
        start_month = 1
        n_years = 4
        end_month = n_years * 12
        max_eft_allowable = 35  # degrees Celsius (HP EFT)
        min_eft_allowable = 5  # degrees Celsius (HP EFT)
        max_height = 135.0  # in meters
        min_height = 60  # in meters
        sim_params = SimulationParameters(
            start_month,
            end_month,
            max_eft_allowable,
            min_eft_allowable,
            max_height,
            min_height,
        )

        # Process loads from file
        # read in the csv file and convert the loads to a list of length 8760
        csv_file = self.test_data_directory / 'Multiyear_Loading_Example.csv'
        raw_lines = csv_file.read_text().split('\n')
        hourly_extraction_ground_loads = [float(x) for x in raw_lines[1:] if x.strip() != '']

        """ Geometric constraints for the `near-square` routine.
        Required geometric constraints for the uniform rectangle design:
          - B
          - length
        """
        # B is already defined above
        number_of_boreholes = 32
        length = length_of_side(number_of_boreholes, b)
        geometric_constraints = GeometricConstraintsNearSquare(b, length)

        # Single U-tube
        # -------------
        # load_years optional parameter is used to determine if there are leap years in the given loads/where they fall
        design_single_u_tube = DesignNearSquare(
            v_flow,
            borehole,
            single_u_tube,
            fluid,
            pipe_single,
            grout,
            soil,
            sim_params,
            geometric_constraints,
            hourly_extraction_ground_loads,
            method=DesignMethodTimeStep.Hybrid,
            flow=flow,
            load_years=[2010, 2011, 2012, 2013],
        )

        # Find the near-square design for a single U-tube and size it.
        tic = clock()  # Clock Start Time
        bisection_search = design_single_u_tube.find_design(disp=True)  # Finding GHE Design
        bisection_search.ghe.compute_g_functions()  # Calculating G-functions for Chosen Design
        bisection_search.ghe.size(
            method=DesignMethodTimeStep.Hybrid
        )  # Calculating the Final Height for the Chosen Design
        toc = clock()  # Clock Stop Time

        # Print Summary of Findings
        subtitle = "* Single U-tube"  # Subtitle for the printed summary
        self.log(subtitle + "\n" + len(subtitle) * "-")
        self.log(f"Calculation time: {toc - tic:0.2f} seconds")
        self.log(f"Height: {bisection_search.ghe.bhe.b.H:0.4f} meters")
        nbh = len(bisection_search.ghe.gFunction.bore_locations)
        self.log(f"Number of boreholes: {nbh}")
        self.log(f"Total Drilling: {bisection_search.ghe.bhe.b.H * nbh:0.1f} meters\n")

        # Generating Output File
        write_output_files(
            bisection_search,
            toc - tic,
            project_name,
            note,
            author,
            iteration_name,
            output_directory=output_file_directory,
            file_suffix="_SU",
            load_method=DesignMethodTimeStep.Hybrid
        )

        # *************************************************************************************************************
        # Double U-tube Example

        note = "Square-Near-Square w/ Multi-year Loading Usage Example: Double U Tube"

        # Double U-tube
        pos_double = Pipe.place_pipes(s, r_out, 2)
        double_u_tube = MultipleUTube
        pipe_double = Pipe(pos_double, r_in, r_out, s, epsilon, k_p, rho_cp_p)

        # Double U-tube
        # -------------
        design_double_u_tube = DesignNearSquare(
            v_flow,
            borehole,
            double_u_tube,
            fluid,
            pipe_double,
            grout,
            soil,
            sim_params,
            geometric_constraints,
            hourly_extraction_ground_loads,
            method=DesignMethodTimeStep.Hybrid,
            flow=flow,
            load_years=[2010, 2011, 2012, 2013],
        )

        # Find the near-square design for a single U-tube and size it.
        tic = clock()  # Clock Start Time
        bisection_search = design_double_u_tube.find_design(disp=True)  # Finding GHE Design
        bisection_search.ghe.compute_g_functions()  # Calculating G-functions for Chosen Design
        bisection_search.ghe.size(
            method=DesignMethodTimeStep.Hybrid
        )  # Calculating the Final Height for the Chosen Design
        toc = clock()  # Clock Stop Time

        # Print Summary of Findings
        subtitle = "* Double U-tube"  # Subtitle for the printed summary
        self.log(subtitle + "\n" + len(subtitle) * "-")
        self.log(f"Calculation time: {toc - tic:0.2f} seconds")
        self.log(f"Height: {bisection_search.ghe.bhe.b.H:0.4f} meters")
        nbh = len(bisection_search.ghe.gFunction.bore_locations)
        self.log(f"Number of boreholes: {nbh}")
        self.log(f"Total Drilling: {bisection_search.ghe.bhe.b.H * nbh:0.1f} meters\n")

        # Generating Output File
        write_output_files(
            bisection_search,
            toc - tic,
            project_name,
            note,
            author,
            iteration_name,
            output_directory=output_file_directory,
            # TODO: Use unique output file names for each test
            file_suffix="_DU",
            load_method=DesignMethodTimeStep.Hybrid,
        )

        # *************************************************************************************************************
        # Coaxial Tube Example

        note = "Square-Near-Square w/ Multi-year Loading Usage Example:Coaxial Tube"

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
        coaxial_tube = CoaxialPipe
        pipe_coaxial = Pipe(
            pos_coaxial, r_inner, r_outer, 0, epsilon, k_p_coax, rho_cp_p
        )

        # Coaxial Tube
        # -------------
        design_coax_tube = DesignNearSquare(
            v_flow,
            borehole,
            coaxial_tube,
            fluid,
            pipe_coaxial,
            grout,
            soil,
            sim_params,
            geometric_constraints,
            hourly_extraction_ground_loads,
            method=DesignMethodTimeStep.Hybrid,
            flow=flow,
            load_years=[2010, 2011, 2012, 2013],
        )

        # Find the near-square design for a single U-tube and size it.
        tic = clock()  # Clock Start Time
        bisection_search = design_coax_tube.find_design(disp=True)  # Finding GHE Design
        bisection_search.ghe.compute_g_functions()  # Calculating G-functions for Chosen Design
        bisection_search.ghe.size(
            method=DesignMethodTimeStep.Hybrid
        )  # Calculating the Final Height for the Chosen Design
        toc = clock()  # Clock Stop Time

        # Print Summary of Findings
        subtitle = "* Coaxial Tube"  # Subtitle for the printed summary
        self.log(subtitle + "\n" + len(subtitle) * "-")
        self.log(f"Calculation time: {toc - tic:0.2f} seconds")
        self.log(f"Height: {bisection_search.ghe.bhe.b.H:0.4f} meters")
        nbh = len(bisection_search.ghe.gFunction.bore_locations)
        self.log(f"Number of boreholes: {nbh}")
        self.log(f"Total Drilling: {bisection_search.ghe.bhe.b.H * nbh:0.1f} meters\n")

        # Generating Output File
        write_output_files(
            bisection_search,
            toc - tic,
            project_name,
            note,
            author,
            iteration_name,
            output_directory=output_file_directory,
            file_suffix="_C",
            load_method=DesignMethodTimeStep.Hybrid
        )
from ghedesigner.borehole import GHEBorehole
from ghedesigner.coordinates import rectangle
from ghedesigner.enums import BHPipeType, TimestepType
from ghedesigner.gfunction import calc_g_func_for_multiple_lengths
from ghedesigner.ground_heat_exchangers import GHE
from ghedesigner.media import Pipe, Soil, Grout, GHEFluid
from ghedesigner.simulation import SimulationParameters
from ghedesigner.tests.ghe_base_case import GHEBaseTest
from ghedesigner.utilities import eskilson_log_times


class TestLiveGFunctionSimAndSize(GHEBaseTest):
    def test_live_g_function_sim_and_size(self):
        # Borehole dimensions
        # -------------------
        h = 96.0  # Borehole length (m)
        d = 2.0  # Borehole buried depth (m)
        r_b = 0.075  # Borehole radius]
        b = 5.0  # Borehole spacing (m)

        # Pipe dimensions
        # ---------------
        r_out = 0.013335  # Pipe outer radius (m)
        r_in = 0.0108  # Pipe inner radius (m)
        s = 0.0323  # Inner-tube to inner-tube Shank spacing (m)
        epsilon = 1.0e-6  # Pipe roughness (m)

        # Pipe positions
        # --------------
        # Single U-tube [(x_in, y_in), (x_out, y_out)]
        pos = Pipe.place_pipes(s, r_out, 1)

        # Thermal conductivities
        # ----------------------
        k_p = 0.4  # Pipe thermal conductivity (W/m.K)
        k_s = 2.0  # Ground thermal conductivity (W/m.K)
        k_g = 1.0  # Grout thermal conductivity (W/m.K)

        # Volumetric heat capacities
        # --------------------------
        rho_cp_p = 1542000.0  # Pipe volumetric heat capacity (J/K.m3)
        rho_cp_s = 2343493.0  # Soil volumetric heat capacity (J/K.m3)
        rho_cp_g = 3901000.0  # Grout volumetric heat capacity (J/K.m3)

        # Thermal properties
        # ------------------
        # Pipe
        pipe = Pipe(pos, r_in, r_out, s, epsilon, k_p, rho_cp_p)
        # Soil
        ugt = 18.3  # Undisturbed ground temperature (degrees Celsius)
        soil = Soil(k_s, rho_cp_s, ugt)
        # Grout
        grout = Grout(k_g, rho_cp_g)

        # Eskilson's original ln(t/ts) values
        log_time = eskilson_log_times()

        # Inputs related to fluid
        # -----------------------
        # Fluid properties
        fluid = GHEFluid(fluid_str="Water", percent=0.0)

        # Coordinates
        nx = 12
        ny = 13
        coordinates = rectangle(nx, ny, b, b)

        # Fluid properties
        v_flow_borehole = 0.2
        # System volumetric flow rate (L/s)
        v_flow_system = v_flow_borehole * float(nx * ny)
        # Total fluid mass flow rate per borehole (kg/s)
        m_flow_borehole = v_flow_borehole / 1000.0 * fluid.rho

        # Define a borehole
        borehole = GHEBorehole(h, d, r_b, x=0.0, y=0.0)

        # Simulation start month and end month
        # --------------------------------
        # Simulation start month and end month
        start_month = 1
        n_years = 20
        end_month = n_years * 12
        # Maximum and minimum allowable fluid temperatures
        max_eft_allowable = 35  # degrees Celsius
        min_eft_allowable = 5  # degrees Celsius
        # Maximum and minimum allowable heights
        max_height = 150  # in meters
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
        hourly_extraction_ground_loads = self.get_atlanta_loads()

        # Calculate a g-function for uniform inlet fluid temperature with
        g_function = calc_g_func_for_multiple_lengths(
            b,
            [h],
            r_b,
            d,
            m_flow_borehole,
            BHPipeType.SINGLEUTUBE,
            log_time,
            coordinates,
            fluid,
            pipe,
            grout,
            soil,
        )

        # --------------------------------------------------------------------------

        # Initialize the GHE object
        ghe = GHE(
            v_flow_system,
            b,
            BHPipeType.SINGLEUTUBE,
            fluid,
            borehole,
            pipe,
            grout,
            soil,
            g_function,
            sim_params,
            hourly_extraction_ground_loads,
        )

        # Simulate after computing just one g-function
        max_hp_eft, min_hp_eft = ghe.simulate(method=TimestepType.HYBRID)

        self.log("Min EFT: {0:0.3f}\nMax EFT: {1:0.3f}".format(min_hp_eft, max_hp_eft))

        # Compute a range of g-functions for interpolation
        h_values = [24.0, 48.0, 96.0, 192.0, 384.0]
        bh_depth = 2.0

        g_function = calc_g_func_for_multiple_lengths(
            b,
            h_values,
            r_b,
            bh_depth,
            m_flow_borehole,
            BHPipeType.SINGLEUTUBE,
            log_time,
            coordinates,
            fluid,
            pipe,
            grout,
            soil,
        )

        # Re-Initialize the GHE object
        ghe = GHE(
            v_flow_system,
            b,
            BHPipeType.SINGLEUTUBE,
            fluid,
            borehole,
            pipe,
            grout,
            soil,
            g_function,
            sim_params,
            hourly_extraction_ground_loads,
        )

        ghe.size(method=TimestepType.HYBRID)

        self.log(f"Height of boreholes: {ghe.bhe.b.H:0.4f}")

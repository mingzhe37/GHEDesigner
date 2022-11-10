import copy
from json import dumps
from pathlib import Path
from typing import Optional

import math
import numpy as np
import pygfunction as gt

from ghedesigner.gfunction import compute_live_g_function
from ghedesigner.ground_heat_exchangers import GHE
from ghedesigner.media import Grout, Pipe, SimulationParameters, Soil
from ghedesigner.rowwise_generation import field_optimization_fr, field_optimization_wp_space_fr
from ghedesigner.utilities import eskilson_log_times, borehole_spacing, check_bracket, sign, DesignMethod


class Bisection1D:
    def __init__(
            self,
            coordinates_domain: list,
            field_descriptors: list,
            v_flow: float,
            borehole: gt.boreholes.Borehole,
            bhe_object,
            fluid: gt.media.Fluid,
            pipe: Pipe,
            grout: Grout,
            soil: Soil,
            sim_params: SimulationParameters,
            hourly_extraction_ground_loads: list,
            method: DesignMethod,
            flow: str = "borehole",
            max_iter=15,
            disp=False,
            search=True,
            field_type="N/A",
            load_years=None,
    ):

        # Take the lowest part of the coordinates domain to be used for the
        # initial setup
        if load_years is None:
            load_years = [2019]
        self.load_years = load_years
        self.searchTracker = []
        coordinates = coordinates_domain[0]
        current_field = field_descriptors[0]
        self.fieldType = field_type
        # Flow rate tracking
        self.V_flow = v_flow
        self.flow = flow
        v_flow_system, m_flow_borehole = self.retrieve_flow(coordinates, fluid.rho)
        self.method = method

        self.log_time = eskilson_log_times()
        self.bhe_object = bhe_object
        self.sim_params = sim_params
        self.hourly_extraction_ground_loads = hourly_extraction_ground_loads
        self.coordinates_domain = coordinates_domain
        self.fieldDescriptors = field_descriptors
        self.max_iter = max_iter
        self.disp = disp

        b = borehole_spacing(borehole, coordinates)

        # Calculate a g-function for uniform inlet fluid temperature with
        # 8 unequal segments using the equivalent solver
        g_function = compute_live_g_function(
            b,
            [borehole.H],
            [borehole.r_b],
            [borehole.D],
            m_flow_borehole,
            self.bhe_object,
            self.log_time,
            coordinates,
            fluid,
            pipe,
            grout,
            soil,
        )

        # Initialize the GHE object
        self.ghe = GHE(
            v_flow_system,
            b,
            bhe_object,
            fluid,
            borehole,
            pipe,
            grout,
            soil,
            g_function,
            sim_params,
            hourly_extraction_ground_loads,
            field_specifier=current_field,
            field_type=field_type,
            load_years=load_years,
        )

        self.calculated_temperatures = {}

        if search:
            self.selection_key, self.selected_coordinates = self.search()

    def retrieve_flow(self, coordinates, rho):
        if self.flow == "borehole":
            v_flow_system = self.V_flow * float(len(coordinates))
            # Total fluid mass flow rate per borehole (kg/s)
            m_flow_borehole = self.V_flow / 1000.0 * rho
        elif self.flow == "system":
            v_flow_system = self.V_flow
            v_flow_borehole = self.V_flow / float(len(coordinates))
            m_flow_borehole = v_flow_borehole / 1000.0 * rho
        else:
            raise ValueError(
                "The flow argument should be either `borehole`" "or `system`."
            )
        return v_flow_system, m_flow_borehole

    def initialize_ghe(self, coordinates, h, field_specifier="N/A"):
        v_flow_system, m_flow_borehole = self.retrieve_flow(
            coordinates, self.ghe.bhe.fluid.rho
        )

        self.ghe.bhe.b.H = h
        borehole = self.ghe.bhe.b
        fluid = self.ghe.bhe.fluid
        pipe = self.ghe.bhe.pipe
        grout = self.ghe.bhe.grout
        soil = self.ghe.bhe.soil

        b = borehole_spacing(borehole, coordinates)

        # Calculate a g-function for uniform inlet fluid temperature with
        # 8 unequal segments using the equivalent solver
        g_function = compute_live_g_function(
            b,
            [borehole.H],
            [borehole.r_b],
            [borehole.D],
            m_flow_borehole,
            self.bhe_object,
            self.log_time,
            coordinates,
            fluid,
            pipe,
            grout,
            soil,
        )

        # Initialize the GHE object
        self.ghe = GHE(
            v_flow_system,
            b,
            self.bhe_object,
            fluid,
            borehole,
            pipe,
            grout,
            soil,
            g_function,
            self.sim_params,
            self.hourly_extraction_ground_loads,
            field_type=self.fieldType,
            field_specifier=field_specifier,
            load_years=self.load_years,
        )

    def calculate_excess(self, coordinates, h, field_specifier="N/A"):
        self.initialize_ghe(coordinates, h, field_specifier=field_specifier)
        # Simulate after computing just one g-function
        max_hp_eft, min_hp_eft = self.ghe.simulate(method=self.method)
        t_excess = self.ghe.cost(max_hp_eft, min_hp_eft)
        self.searchTracker.append([field_specifier, t_excess, max_hp_eft, min_hp_eft])

        # This is more of a debugging statement. May remove it in the future.
        # Perhaps there becomes a debug: bool option in the API.
        # if self.disp:
        #     print('Min EFT: {}\nMax EFT: {}'.format(min_HP_EFT, max_HP_EFT))

        return t_excess

    def search(self):

        x_l_idx = 0
        x_r_idx = len(self.coordinates_domain) - 1
        if self.disp:
            print("Do some initial checks before searching.")
        # Get the lowest possible excess temperature from minimum height at the
        # smallest location in the domain
        t_0_lower = self.calculate_excess(
            self.coordinates_domain[x_l_idx],
            self.sim_params.min_Height,
            field_specifier=self.fieldDescriptors[x_l_idx],
        )
        t_0_upper = self.calculate_excess(
            self.coordinates_domain[x_l_idx],
            self.sim_params.max_Height,
            field_specifier=self.fieldDescriptors[x_l_idx],
        )
        t_m1 = self.calculate_excess(
            self.coordinates_domain[x_r_idx],
            self.sim_params.max_Height,
            field_specifier=self.fieldDescriptors[x_r_idx],
        )

        self.calculated_temperatures[x_l_idx] = t_0_upper
        self.calculated_temperatures[x_r_idx] = t_m1

        if check_bracket(sign(t_0_lower), sign(t_0_upper)):
            if self.disp:
                print("Size between min and max of lower bound in domain.")
            self.initialize_ghe(self.coordinates_domain[0], self.sim_params.max_Height)
            return 0, self.coordinates_domain[0]
        elif check_bracket(sign(t_0_upper), sign(t_m1)):
            if self.disp:
                print("Perform the integer bisection search routine.")
            pass
        else:
            # This domain does not bracket the solution
            if t_0_upper < 0.0 and t_m1 < 0.0:
                msg = (
                    "Based on the loads provided, the excess temperatures "
                    "for the minimum and maximum number of boreholes falls "
                    'below 0. This means that the loads are "miniscule" or '
                    "that the lower end of the domain needs to contain "
                    "less boreholes."
                )
                raise ValueError(msg)
            if t_0_upper > 0.0 and t_m1 > 0.0:
                msg = (
                    "Based on the loads provided, the excess temperatures "
                    "for the minimum and maximum number of boreholes falls "
                    'above 0. This means that the loads are "astronomical" '
                    "or that the higher end of the domain needs to contain "
                    "more boreholes. Consider increasing the available land"
                    " area, or decreasing the minimum allowable borehole "
                    "spacing."
                )
                raise ValueError(msg)
            return None, None

        if self.disp:
            print("Beginning bisection search...")

        x_l_sign = sign(t_0_upper)
        # xR_sign = sign(T_m1)

        i = 0

        while i < self.max_iter:
            c_idx = int(np.ceil((x_l_idx + x_r_idx) / 2))
            # if the solution is no longer making progress break the while
            if c_idx == x_l_idx or c_idx == x_r_idx:
                break

            c_t_excess = self.calculate_excess(
                self.coordinates_domain[c_idx],
                self.sim_params.max_Height,
                field_specifier=self.fieldDescriptors[c_idx],
            )

            self.calculated_temperatures[c_idx] = c_t_excess
            c_sign = sign(c_t_excess)

            if c_sign == x_l_sign:
                x_l_idx = copy.deepcopy(c_idx)
            else:
                x_r_idx = copy.deepcopy(c_idx)

            i += 1

        coordinates = self.coordinates_domain[i]

        h = self.sim_params.max_Height

        self.calculate_excess(coordinates, h, field_specifier=self.fieldDescriptors[i])
        # Make sure the field being returned pertains to the index which is the
        # closest to 0 but also negative (the maximum of all 0 or negative
        # excess temperatures)
        keys = list(self.calculated_temperatures.keys())
        values = list(self.calculated_temperatures.values())

        negative_excess_values = [v for v in values if v <= 0.0]

        excess_of_interest = max(negative_excess_values)
        idx = values.index(excess_of_interest)
        selection_key = keys[idx]
        selected_coordinates = self.coordinates_domain[selection_key]

        self.initialize_ghe(
            selected_coordinates, h, field_specifier=self.fieldDescriptors[selection_key]
        )

        return selection_key, selected_coordinates


# This is the search algorithm used for finding row-wise fields
class RowWiseModifiedBisectionSearch:
    def __init__(
            self,
            v_flow: float,
            borehole: gt.boreholes.Borehole,
            bhe_object,
            fluid: gt.media.Fluid,
            pipe: Pipe,
            grout: Grout,
            soil: Soil,
            sim_params: SimulationParameters,
            hourly_extraction_ground_loads: list,
            geometric_constraints,
            method: DesignMethod,
            flow: str = "borehole",
            max_iter: int = 10,
            disp: bool = False,
            search: bool = True,
            advanced_tracking: bool = True,
            field_type: str = "rowwise",
            load_years=None,
            e_t: float = 1e-10,
            b_r_point=None,
            b_r_removal_method: str = "CloseToCorner",
            exhaustive_fields_to_check: int = 10,
            use_perimeter: bool = True,
    ):

        # Take the lowest part of the coordinates domain to be used for the
        # initial setup
        if b_r_point is None:
            b_r_point = [0.0, 0.0]
        if load_years is None:
            load_years = [2019]
        self.load_years = load_years
        self.fluid = fluid
        self.pipe = pipe
        self.grout = grout
        self.soil = soil
        self.borehole = borehole
        self.geometricConstraints = geometric_constraints
        self.searchTracker = []
        self.fieldType = field_type
        # Flow rate tracking
        self.V_flow = v_flow
        self.flow = flow
        self.method = method
        self.log_time = eskilson_log_times()
        self.bhe_object = bhe_object
        self.sim_params = sim_params
        self.hourly_extraction_ground_loads = hourly_extraction_ground_loads
        self.max_iter = max_iter
        self.disp = disp
        self.ghe: Optional[GHE] = None
        self.calculated_temperatures = {}
        # self.advanced_tracking = advanced_tracking
        if advanced_tracking:
            self.advanced_tracking = [
                ["TargetSpacing", "Field Specifier", "nbh", "ExcessTemperature"]
            ]
            self.checkedFields = []
        if search:
            self.selected_coordinates, self.selected_specifier = self.search(
                e_t=e_t,
                b_r_point=b_r_point,
                b_r_removal_method=b_r_removal_method,
                exhaustive_fields_to_check=exhaustive_fields_to_check,
                use_perimeter=use_perimeter,
            )
            self.initialize_ghe(
                self.selected_coordinates,
                self.sim_params.max_Height,
                field_specifier=self.selected_specifier,
            )

    def retrieve_flow(self, coordinates, rho):
        if self.flow == "borehole":
            v_flow_system = self.V_flow * float(len(coordinates))
            # Total fluid mass flow rate per borehole (kg/s)
            m_flow_borehole = self.V_flow / 1000.0 * rho
        elif self.flow == "system":
            v_flow_system = self.V_flow
            v_flow_borehole = self.V_flow / float(len(coordinates))
            m_flow_borehole = v_flow_borehole / 1000.0 * rho
        else:
            raise ValueError(
                "The flow argument should be either `borehole`" "or `system`."
            )
        return v_flow_system, m_flow_borehole

    def initialize_ghe(self, coordinates, h, field_specifier="N/A"):
        v_flow_system, m_flow_borehole = self.retrieve_flow(coordinates, self.fluid.rho)

        self.borehole.H = h
        borehole = self.borehole
        fluid = self.fluid
        pipe = self.pipe
        grout = self.grout
        soil = self.soil

        b = borehole_spacing(borehole, coordinates)

        # Calculate a g-function for uniform inlet fluid temperature with
        # 8 unequal segments using the equivalent solver
        g_function = compute_live_g_function(
            b,
            [borehole.H],
            [borehole.r_b],
            [borehole.D],
            m_flow_borehole,
            self.bhe_object,
            self.log_time,
            coordinates,
            fluid,
            pipe,
            grout,
            soil,
        )

        # Initialize the GHE object
        self.ghe = GHE(
            v_flow_system,
            b,
            self.bhe_object,
            fluid,
            borehole,
            pipe,
            grout,
            soil,
            g_function,
            self.sim_params,
            self.hourly_extraction_ground_loads,
            field_type=self.fieldType,
            field_specifier=field_specifier,
            load_years=self.load_years,
        )

    def calculate_excess(self, coordinates, h, field_specifier="N/A"):
        self.initialize_ghe(coordinates, h, field_specifier=field_specifier)
        # Simulate after computing just one g-function
        max_hp_eft, min_hp_eft = self.ghe.simulate(method=self.method)
        t_excess = self.ghe.cost(max_hp_eft, min_hp_eft)
        self.searchTracker.append([field_specifier, t_excess, max_hp_eft, min_hp_eft])

        # This is more of a debugging statement. May remove it in the future.
        # Perhaps there becomes a debug: bool option in the API.
        # if self.disp:
        #     print('Min EFT: {}\nMax EFT: {}'.format(min_HP_EFT, max_HP_EFT))

        return t_excess

    def search(
            self,
            e_t=1e-10,
            b_r_point=None,
            b_r_removal_method="CloseToCorner",
            exhaustive_fields_to_check=10,
            use_perimeter=True,
    ):
        # Copy all the geometric constraints to local variables
        if b_r_point is None:
            b_r_point = [0.0, 0.0]
        spacing_start = self.geometricConstraints.spacStart
        spacing_stop = self.geometricConstraints.spacStop
        spacing_step = self.geometricConstraints.spacStep
        rotate_step = self.geometricConstraints.rotateStep
        prop_bound = self.geometricConstraints.propBound
        ng_zones = self.geometricConstraints.ngZones
        rotate_start = self.geometricConstraints.rotateStart
        rotate_stop = self.geometricConstraints.rotateStop
        p_spacing = self.geometricConstraints.pSpac

        selected_coordinates = None
        selected_specifier = None
        selected_temp_excess = None
        selected_spacing = None

        # Check The Upper and Lower Bounds

        # Generate Fields
        if use_perimeter:
            upper_field, upper_field_specifier = field_optimization_wp_space_fr(
                p_spacing,
                spacing_start,
                rotate_step,
                prop_bound,
                ng_zones=ng_zones,
                rotate_start=rotate_start,
                rotate_stop=rotate_stop,
            )
            lower_field, lower_field_specifier = field_optimization_wp_space_fr(
                p_spacing,
                spacing_stop,
                rotate_step,
                prop_bound,
                ng_zones=ng_zones,
                rotate_start=rotate_start,
                rotate_stop=rotate_stop,
            )
        else:
            upper_field, upper_field_specifier = field_optimization_fr(
                spacing_start,
                rotate_step,
                prop_bound,
                ng_zones=ng_zones,
                rotate_start=rotate_start,
                rotate_stop=rotate_stop,
            )
            lower_field, lower_field_specifier = field_optimization_fr(
                spacing_stop,
                rotate_step,
                prop_bound,
                ng_zones=ng_zones,
                rotate_start=rotate_start,
                rotate_stop=rotate_stop,
            )
        # Get Excess Temperatures
        t_upper = self.calculate_excess(
            upper_field, self.sim_params.max_Height, field_specifier=upper_field_specifier
        )
        t_lower = self.calculate_excess(
            lower_field, self.sim_params.max_Height, field_specifier=lower_field_specifier
        )

        if self.advanced_tracking:
            self.advanced_tracking.append(
                [spacing_start, upper_field_specifier, len(upper_field), t_upper]
            )
            self.advanced_tracking.append(
                [spacing_stop, lower_field_specifier, len(lower_field), t_lower]
            )
            self.checkedFields.append(upper_field)
            self.checkedFields.append(lower_field)

        # If the excess temperature is >0 utilizing the largest field and largest depth, then notify the user that
        # the given constraints cannot find a satisfactory field.
        if t_upper > 0.0 and t_lower > 0.0:
            msg = (
                "Based on the loads provided, the excess temperatures for the minimum and maximum number of boreholes"
                "fall above 0. This means that the loads are too large for the corresponding simulation parameters."
                "Please double check the loadings or adjust those parameters."
            )
            raise ValueError(msg)
        # If the excess temperature is > 0 when utilizing the largest field and depth but < 0 when using the largest
        # depth and smallest field, then fields should be searched between the two target depths.
        elif t_upper < 0.0 < t_lower:
            # This search currently works by doing a slightly modified bisection search where the "steps" are the set
            # by the "spacing_step" variable. The steps are used to check fields on either side of the field found by
            # doing a normal bisection search. These extra fields are meant to help prevent falling into local minima
            # (although this will still happen sometimes).
            i = 0
            spacing_high = spacing_start
            spacing_low = spacing_stop
            low_e = t_upper
            high_e = t_lower
            spacing_m = (spacing_stop + spacing_start) * 0.5
            while i < self.max_iter:
                print("Bisection Search Iteration: ", i)
                # Getting Three Middle Field
                if use_perimeter:
                    f1, f1_specifier = field_optimization_wp_space_fr(
                        p_spacing,
                        spacing_m,
                        rotate_step,
                        prop_bound,
                        ng_zones=ng_zones,
                        rotate_start=rotate_start,
                        rotate_stop=rotate_stop,
                    )
                else:
                    f1, f1_specifier = field_optimization_fr(
                        spacing_m,
                        rotate_step,
                        prop_bound,
                        ng_zones=ng_zones,
                        rotate_start=rotate_start,
                        rotate_stop=rotate_stop,
                    )

                # Getting the three field's excess temperature
                t_e1 = self.calculate_excess(
                    f1, self.sim_params.max_Height, field_specifier=f1_specifier
                )

                if self.advanced_tracking:
                    self.advanced_tracking.append([spacing_m, f1_specifier, len(f1), t_e1])
                    self.checkedFields.append(f1)
                if t_e1 <= 0.0:
                    spacing_high = spacing_m
                    high_e = t_e1
                    selected_specifier = f1_specifier
                else:
                    spacing_low = spacing_m
                    low_e = t_e1

                spacing_m = (spacing_low + spacing_high) * 0.5
                if abs(low_e - high_e) < e_t:
                    break

                i += 1

            # Now Check fields that have a higher target spacing to double-check that none of them would work:
            spacing_l = spacing_step + spacing_high
            target_spacings = []
            current_spacing = spacing_high
            spacing_change = (spacing_l - current_spacing) / exhaustive_fields_to_check
            while current_spacing <= spacing_l:
                target_spacings.append(current_spacing)
                current_spacing += spacing_change
            best_field = None
            best_drilling = float("inf")
            best_excess = None
            best_spacing = None
            for i in range(len(target_spacings)):
                if use_perimeter:
                    field, f_s = field_optimization_wp_space_fr(
                        p_spacing,
                        target_spacings[i],
                        rotate_step,
                        prop_bound,
                        ng_zones=ng_zones,
                        rotate_start=rotate_start,
                        rotate_stop=rotate_stop,
                    )
                else:
                    field, f_s = field_optimization_fr(
                        target_spacings[i],
                        rotate_step,
                        prop_bound,
                        ng_zones=ng_zones,
                        rotate_start=rotate_start,
                        rotate_stop=rotate_stop,
                    )
                t_e = self.calculate_excess(
                    field, self.sim_params.max_Height, field_specifier=f_s
                )

                if self.advanced_tracking:
                    self.advanced_tracking.append(
                        [target_spacings[i], f_s, len(field), t_e]
                    )
                    self.checkedFields.append(field)

                self.initialize_ghe(
                    field, self.sim_params.max_Height, field_specifier=f_s
                )
                self.ghe.compute_g_functions()
                self.ghe.size(method=DesignMethod.Hybrid)
                h = self.ghe.average_height()
                total_drilling = h * len(field)
                if best_field is None:
                    best_field = field
                    best_drilling = total_drilling
                    best_excess = t_e
                    best_spacing = target_spacings[i]
                else:
                    if t_e <= 0.0 and total_drilling < best_drilling:
                        best_drilling = total_drilling
                        best_field = field
                        best_excess = t_e
                        best_spacing = target_spacings[i]
            selected_coordinates = best_field
            selected_temp_excess = best_excess
            selected_spacing = best_spacing

        # If the excess temperature is < 0 when utilizing the largest depth and the smallest field, it is most likely
        # in the user's best interest to return a field smaller than the smallest one. This is done by removing
        # boreholes from the field.
        elif t_lower < 0.0 and t_upper < 0.0:

            original_coordinates = copy.deepcopy(lower_field)

            # Function For Sorting Boreholes Based on Proximity to a Point
            def point_sort(target_point, other_points, method="ascending"):
                def dist(o_p):
                    return math.sqrt(
                        (target_point[0] - o_p[0]) * (target_point[0] - o_p[0])
                        + (target_point[1] - o_p[1]) * (target_point[1] - o_p[1])
                    )

                distances = map(dist, other_points)
                if method == "ascending":
                    return [x for _, x in sorted(zip(distances, other_points))]
                elif method == "descending":
                    return [
                        x for _, x in sorted(zip(distances, other_points), reverse=True)
                    ]

            if b_r_removal_method == "CloseToCorner":
                starting_field = point_sort(
                    original_coordinates[0], lower_field, method="descending"
                )
            elif b_r_removal_method == "CloseToPoint":
                starting_field = point_sort(b_r_point, lower_field, method="descending")
            elif b_r_removal_method == "FarFromPoint":
                starting_field = point_sort(b_r_point, lower_field, method="ascending")
            elif b_r_removal_method == "RowRemoval":
                starting_field = lower_field
            else:
                msg = (
                        b_r_removal_method
                        + " is not a valid method for removing boreholes. The valid methods are: "
                          "CloseToCorner, CloseToPoint, FarFromPoint, and RowRemoval."
                )
                raise ValueError(msg)

            # Check if a 1X1 field is satisfactory
            t_e_single = self.calculate_excess(
                [[0, 0]], self.sim_params.max_Height, field_specifier="1X1"
            )
            if self.advanced_tracking:
                self.advanced_tracking.append(["N/A", "1X1", 1, t_e_single])
                self.checkedFields.append([[0, 0]])
            if t_e_single <= 0:
                selected_temp_excess = t_e_single
                selected_specifier = "1X1"
                selected_coordinates = starting_field[len(starting_field) - 1:]
                selected_spacing = spacing_stop
            else:
                # Perform a bisection search between nbh values to find the smallest satisfactory field
                nbh_max = len(starting_field)
                nbh_min = 1
                nbh_start = nbh_max
                # continueLoop = True
                # highT_e = T_lower
                selected_specifier = lower_field_specifier
                i = 0
                while i < self.max_iter:
                    nbh = (nbh_max + nbh_min) // 2
                    current_field = starting_field[nbh_start - nbh:]
                    f_s = lower_field_specifier + "_BR{}".format(nbh_start - nbh)
                    t_e = self.calculate_excess(
                        current_field, self.sim_params.max_Height, field_specifier=f_s
                    )
                    if self.advanced_tracking:
                        self.advanced_tracking.append(
                            [spacing_stop, lower_field_specifier + "_" + str(nbh), nbh, t_e]
                        )
                        self.checkedFields.append(current_field)
                    if t_e <= 0.0:
                        # highT_e = T_e
                        nbh_max = nbh
                        selected_coordinates = current_field
                        selected_specifier = f_s
                        selected_temp_excess = t_e
                        selected_spacing = spacing_stop
                    else:
                        nbh_min = nbh
                    if (nbh_max - nbh_min) <= 1:
                        break
                    i += 1
        # If none of the options above have been true, then there is most likely an issue with the excess temperature
        # calculation.
        else:
            msg = (
                "There seems to be an issue calculating excess temperatures. Check that you have the correct"
                "package version. If this is a recurring issue, please contact the current package management for "
                "assistance."
            )
            raise ValueError(msg)
        if self.advanced_tracking:
            self.advanced_tracking.append(
                [
                    selected_spacing,
                    selected_specifier,
                    len(selected_coordinates),
                    selected_temp_excess,
                ]
            )
            self.checkedFields.append(selected_coordinates)
        return selected_coordinates, selected_specifier


class Bisection2D(Bisection1D):
    def __init__(
            self,
            coordinates_domain_nested: list,
            field_descriptors: list,
            v_flow: float,
            borehole: gt.boreholes.Borehole,
            bhe_object,
            fluid: gt.media.Fluid,
            pipe: Pipe,
            grout: Grout,
            soil: Soil,
            sim_params: SimulationParameters,
            hourly_extraction_ground_loads: list,
            method: DesignMethod,
            flow: str = "borehole",
            max_iter=15,
            disp=False,
            field_type="N/A",
            load_years=None,
    ):
        if load_years is None:
            load_years = [2019]
        if disp:
            print("Note: This routine requires a nested bisection search.")
        self.load_years = load_years
        # Get a coordinates domain for initialization
        coordinates_domain = coordinates_domain_nested[0]
        # print("Coordinate Dimensions",len(coordinates_domain),len(coordinates_domain[0]))
        Bisection1D.__init__(
            self,
            coordinates_domain,
            field_descriptors[0],
            v_flow,
            borehole,
            bhe_object,
            fluid,
            pipe,
            grout,
            soil,
            sim_params,
            hourly_extraction_ground_loads,
            method=method,
            flow=flow,
            max_iter=max_iter,
            disp=disp,
            search=False,
            field_type=field_type,
            load_years=load_years,
        )

        self.coordinates_domain_nested = []
        self.calculated_temperatures_nested = []
        # Tack on one borehole at the beginning to provide a high excess
        # temperature
        outer_domain = [coordinates_domain_nested[0][0]]
        for i in range(len(coordinates_domain_nested)):
            outer_domain.append(coordinates_domain_nested[i][-1])

        self.coordinates_domain = outer_domain

        selection_key, _ = self.search()

        self.calculated_temperatures_nested.append(
            copy.deepcopy(self.calculated_temperatures)
        )

        # We tacked on one borehole to the beginning, so we need to subtract 1
        # on the index
        inner_domain = coordinates_domain_nested[selection_key - 1]
        self.coordinates_domain = inner_domain
        self.fieldDescriptors = field_descriptors[selection_key - 1]

        # Reset calculated temperatures
        self.calculated_temperatures = {}

        self.selection_key, self.selected_coordinates = self.search()


class BisectionZD(Bisection1D):
    def __init__(
            self,
            coordinates_domain_nested: list,
            field_descriptors: list,
            v_flow: float,
            borehole: gt.boreholes.Borehole,
            bhe_object,
            fluid: gt.media.Fluid,
            pipe: Pipe,
            grout: Grout,
            soil: Soil,
            sim_params: SimulationParameters,
            hourly_extraction_ground_loads: list,
            method: DesignMethod,
            flow: str = "borehole",
            max_iter=15,
            disp=False,
            field_type="N/A",
            load_years=None,
    ):
        if load_years is None:
            load_years = [2019]
        if disp:
            print(
                "Note: This design routine currently requires several "
                "bisection searches."
            )

        # Get a coordinates domain for initialization
        coordinates_domain = coordinates_domain_nested[0]
        Bisection1D.__init__(
            self,
            coordinates_domain,
            field_descriptors[0],
            v_flow,
            borehole,
            bhe_object,
            fluid,
            pipe,
            grout,
            soil,
            sim_params,
            hourly_extraction_ground_loads,
            method=method,
            flow=flow,
            max_iter=max_iter,
            disp=disp,
            search=False,
            field_type=field_type,
            load_years=load_years,
        )

        self.coordinates_domain_nested = coordinates_domain_nested
        self.nested_fieldDescriptors = field_descriptors
        self.calculated_temperatures_nested = {}
        # Tack on one borehole at the beginning to provide a high excess
        # temperature
        outer_domain = [coordinates_domain_nested[0][0]]
        outer_descriptors = [field_descriptors[0][0]]
        for i in range(len(coordinates_domain_nested)):
            outer_domain.append(coordinates_domain_nested[i][-1])
            outer_descriptors.append(field_descriptors[i][-1])

        self.coordinates_domain = outer_domain
        self.fieldDescriptors = outer_descriptors

        self.selection_key_outer, _ = self.search()
        if self.selection_key_outer > 0:
            self.selection_key_outer -= 1
        self.calculated_heights = {}

        self.selection_key, self.selected_coordinates = self.search_successive()

    def search_successive(self, max_iter=None):
        if max_iter is None:
            max_iter = self.selection_key_outer + 7

        i = self.selection_key_outer

        old_height = 99999

        while i < len(self.coordinates_domain_nested) and i < max_iter:

            self.coordinates_domain = self.coordinates_domain_nested[i]
            self.fieldDescriptors = self.nested_fieldDescriptors[i]
            self.calculated_temperatures = {}
            try:
                selection_key, selected_coordinates = self.search()
            except ValueError:
                break
            self.calculated_temperatures_nested[i] = copy.deepcopy(
                self.calculated_temperatures
            )

            self.ghe.compute_g_functions()
            self.ghe.size(method=DesignMethod.Hybrid)

            nbh = len(selected_coordinates)
            total_drilling = float(nbh) * self.ghe.bhe.b.H
            self.calculated_heights[i] = total_drilling

            if old_height < total_drilling:
                break
            else:
                old_height = copy.deepcopy(total_drilling)

            i += 1

        keys = list(self.calculated_heights.keys())
        values = list(self.calculated_heights.values())

        minimum_total_drilling = min(values)
        idx = values.index(minimum_total_drilling)
        selection_key_outer = keys[idx]
        self.calculated_temperatures = copy.deepcopy(
            self.calculated_temperatures_nested[selection_key_outer]
        )

        keys = list(self.calculated_temperatures.keys())
        values = list(self.calculated_temperatures.values())

        negative_excess_values = [
            values[i] for i in range(len(values)) if values[i] <= 0.0
        ]

        excess_of_interest = max(negative_excess_values)
        idx = values.index(excess_of_interest)
        selection_key = keys[idx]
        selected_coordinates = self.coordinates_domain_nested[selection_key_outer][
            selection_key
        ]

        self.initialize_ghe(
            selected_coordinates,
            self.sim_params.max_Height,
            field_specifier=self.nested_fieldDescriptors[selection_key_outer][
                selection_key
            ],
        )
        self.ghe.compute_g_functions()
        self.ghe.size(method=DesignMethod.Hybrid)

        return selection_key, selected_coordinates


# The following functions are utility functions specific to search_routines.py
# ------------------------------------------------------------------------------
def oak_ridge_export(bisection_search, file_path: Path):
    # Dictionary for export
    d = dict()
    d["borehole_length"] = bisection_search.ghe.bhe.b.H
    d["number_of_boreholes"] = len(bisection_search.selected_coordinates)
    d["g_function_pairs"] = []
    d["single_u_tube"] = {}

    # create a local single U-tube object
    bhe_eq = bisection_search.ghe.bhe_eq
    d["single_u_tube"]["r_b"] = bhe_eq.borehole.r_b  # Borehole radius
    d["single_u_tube"]["r_in"] = bhe_eq.r_in  # Inner pipe radius
    d["single_u_tube"]["r_out"] = bhe_eq.r_out  # Outer pipe radius
    # Note: Shank spacing or center pipe positions could be used
    d["single_u_tube"]["s"] = bhe_eq.pipe.s  # Shank spacing (tube-to-tube)
    d["single_u_tube"]["pos"] = bhe_eq.pos  # Center of the pipes
    d["single_u_tube"][
        "m_flow_borehole"
    ] = bhe_eq.m_flow_borehole  # mass flow rate of the borehole
    d["single_u_tube"]["k_g"] = bhe_eq.grout.k  # Grout thermal conductivity
    d["single_u_tube"]["k_s"] = bhe_eq.soil.k  # Soil thermal conductivity
    d["single_u_tube"]["k_p"] = bhe_eq.pipe.k  # Pipe thermal conductivity

    # create a local ghe object
    ghe = bisection_search.ghe
    h = ghe.bhe.b.H
    b_over_h = ghe.B_spacing / h
    g = ghe.grab_g_function(b_over_h)

    total_g_values = g.x.size
    number_lts_g_values = 27
    number_sts_g_values = 30
    sts_step_size = int(
        np.floor((total_g_values - number_lts_g_values) / number_sts_g_values).tolist()
    )
    lntts = []
    g_values = []
    for i in range(1, (total_g_values - number_lts_g_values), sts_step_size):
        lntts.append(g.x[i].tolist())
        g_values.append(g.y[i].tolist())
    lntts += g.x[total_g_values - number_lts_g_values: total_g_values].tolist()
    g_values += g.y[total_g_values - number_lts_g_values: total_g_values].tolist()

    for lntts_val, g_val in zip(lntts, g_values):
        d["g_function_pairs"].append({"ln_tts": lntts_val, "g_value": g_val})

    file_path.write_text(dumps(d, indent=4))
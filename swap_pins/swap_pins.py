#  action_swap_pins.py
#
# Copyright (C) 2018 Mitja Nemec
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

import pcbnew
import os
import math
from operator import itemgetter
import re
import logging
import sys

logger = logging.getLogger(__name__)


def swap(board, pad_1, pad_2):
    logger.info("Starting swap_pins")
    footprint = pad_2.GetParent().GetReference()
    # get respective nets
    net_1 = pad_1.GetNet()
    net_2 = pad_2.GetNet()
    pad_1_name = pad_1.GetName()
    pad_2_name = pad_2.GetName()
    net_name_1 = net_1.GetNetname().split('/')[-1]
    net_name_2 = net_2.GetNetname().split('/')[-1]

    logger.info("Swaping pins: " + pad_1_name + ", " + pad_2_name +
                "on: " + footprint + " on nets: " + net_name_1 + ", " + net_name_2)

    # Find the sch file that has this symbol
    main_sch_file = os.path.abspath(str(board.GetFileName()).replace(".kicad_pcb", ".sch"))
    logger.info("main sch file is: " + main_sch_file)
    all_sch_files = []
    all_sch_files = find_all_sch_files(main_sch_file, all_sch_files)
    all_sch_files = list(set(all_sch_files))
    for sch_file in all_sch_files:
        with open(sch_file) as f:
            current_sch_file = f.read()
        if footprint in current_sch_file:
            sch_file_to_modify = sch_file

    logger.info("Sch file to modify: " + sch_file_to_modify)
    # open the schematics, find symbol, find the pins and nearbywires connected to the respective nets
    with open(sch_file_to_modify) as f:
        sch_file = f.read()

    # find both net names and their locations
    closest_label_1 = find_closest_label(sch_file, footprint, net_name_1)
    logger.info("Found closest label for " + net_name_1 + " at (" + str(closest_label_1[0][0]) + ", "
                + str(closest_label_1[0][1]) + ")")
    closest_label_2 = find_closest_label(sch_file, footprint, net_name_2)
    logger.info("Found closest label for " + net_name_2 + " at (" + str(closest_label_2[0][0]) + ", "
                + str(closest_label_2[0][1]) + ")")

    logger.info("Swapping labels")
    # swap netnames in schematics
    sch_file_temp = sch_file[0:closest_label_1[0][2]]\
                  + net_name_2\
                  + sch_file[closest_label_1[0][2]+len(net_name_2):]
    sch_file_out = sch_file_temp[0:closest_label_2[0][2]]\
                 + net_name_1\
                 + sch_file_temp[closest_label_2[0][2]+len(net_name_1):]

    # save schematics
    if __name__ == "__main__":
        sch_file_to_write = os.path.join(os.path.dirname(sch_file_to_modify), 'temp_' + os.path.basename(sch_file_to_modify))
    else:
        sch_file_to_write = sch_file_to_modify
    with open(sch_file_to_write, 'w') as f:
        f.write(sch_file_out)
    logger.info("Saved the schematics.")

    # swap nets in layout
    # Select PADa -> Properties.Copy NetName
    pad_2.SetNet(net_1)
    pad_1.SetNet(net_2)

    # save board
    if __name__ == "__main__":
        pcb_file_to_write = 'temp_' + board.GetFileName()
        pcbnew.SaveBoard(pcb_file_to_write, board)
    logger.info("Saved the layout.")


def find_closest_label(sch_file, footprint, net):
    label_locations = find_all(sch_file, net)
    logger.info("Searching for the closest label for " + net + " to " + footprint)
    labels = []
    for loc_end in label_locations:
        # find position of a label
        loc_begin = sch_file[0:loc_end].rfind('Text Label')
        if loc_begin == -1:
            loc_begin = sch_file[0:loc_end].rfind('Text GLabel')
        if loc_begin == -1:
            loc_begin = sch_file[0:loc_end].rfind('Text HLabel')

        label_data = sch_file[loc_begin:loc_end].split()
        labels.append((float(label_data[2]), float(label_data[3]), loc_end))
        logger.info("Found label at: (" + label_data[2] + ", " + label_data[3] + ")")

    if not labels:
        raise ValueError("No labels for net: " + net + " found on sheet: " + sch_file)

    # find component location
    component_name_index = sch_file.find(footprint)
    componend_description_start = sch_file[0:component_name_index].rfind('$Comp')
    componend_description_end = sch_file[component_name_index:-1].find('$EndComp')
    component_data = sch_file[componend_description_start:componend_description_end].split('\n')
    for data in component_data:
        if data[0] == 'P':
            component_location = (float(data.split()[1]), float(data.split()[2]))
            break

    logger.info("Component location: (" + str(component_location[0]) + " ," + str(component_location[0]) + ")")

    # find closest label
    distances = []
    for label in labels:
        distances.append((label, get_distance((label[0], label[1]), component_location)))
    if len(distances) == 1:
        closest_label = distances[0]
    else:
        closest_label = min(distances, key=itemgetter(1))

    return closest_label


def get_distance(point1, point2):
    return math.hypot(point1[0]-point2[0], point1[1]-point2[1])


def find_all(a_str, sub):
    start = 0
    while True:
        start = a_str.find(sub, start)
        if start == -1:
            return
        yield start
        start += len(sub)


def extract_subsheets(filename):
    with open(filename) as f:
        file_folder = os.path.dirname(os.path.abspath(filename))
        file_lines = f.read()
    # alternative solution
    # extract all sheet references
    sheet_indices = [m.start() for m in re.finditer('\$Sheet', file_lines)]
    endsheet_indices = [m.start() for m in re.finditer('\$EndSheet', file_lines)]

    if len(sheet_indices) != len(endsheet_indices):
        raise LookupError("Schematic page contains errors")

    sheet_locations = zip(sheet_indices, endsheet_indices)
    for sheet_location in sheet_locations:
        sheet_reference = file_lines[sheet_location[0]:sheet_location[1]].split('\n')
        for line in sheet_reference:
            if line.startswith('F1 '):
                subsheet_path = line.split()[1].rstrip("\"").lstrip("\"")
                subsheet_line = file_lines.split("\n").index(line)
                if not os.path.isabs(subsheet_path):
                    # check if path is encoded with variables
                    if "${" in subsheet_path:
                        start_index = subsheet_path.find("${") + 2
                        end_index = subsheet_path.find("}")
                        env_var = subsheet_path[start_index:end_index]
                        path = os.getenv(env_var)
                        # if variable is not defined rasie an exception
                        if path is None:
                            raise LookupError("Can not find subsheet: " + subsheet_path)
                        # replace variable with full path
                        subsheet_path = subsheet_path.replace("${", "") \
                            .replace("}", "") \
                            .replace("env_var", path)

                # if path is still not absolute, then it is relative to project
                if not os.path.isabs(subsheet_path):
                    subsheet_path = os.path.join(file_folder, subsheet_path)

                subsheet_path = os.path.normpath(subsheet_path)
                # found subsheet reference go for the next one, no need to parse further
                break
        yield subsheet_path, subsheet_line


def find_all_sch_files(filename, list_of_files):
    list_of_files.append(filename)
    for sheet, line_nr in extract_subsheets(filename):
        logger.info("found subsheet:\n\t" + sheet +
                    "\n in:\n\t" + filename + ", line: " + str(line_nr))
        seznam = find_all_sch_files(sheet, list_of_files)
        list_of_files = seznam
    return list_of_files


def main():
    test = 'local'  # local global hierarchical
    if test == 'local':
        board = pcbnew.LoadBoard('swap_pins_test.kicad_pcb')
        mod = board.FindModuleByReference('U201')
        pads = mod.Pads()
        for pad in pads:
            if pad.GetPadName() == u'21':
                pad1 = pad
            if pad.GetPadName() == u'22':
                pad2 = pad
        pass
        swap(board, pad1, pad2)
    if test == 'hierarchical':
        board = pcbnew.LoadBoard('swap_pins_test.kicad_pcb')
        mod = board.FindModuleByReference('U301')
        pads = mod.Pads()
        for pad in pads:
            if pad.GetPadName() == u'17':
                pad1 = pad
            if pad.GetPadName() == u'18':
                pad2 = pad
        pass
        swap(board, pad1, pad2)
    if test == 'global':
        board = pcbnew.LoadBoard('swap_pins_test.kicad_pcb')
        mod = board.FindModuleByReference('U101')
        pads = mod.Pads()
        for pad in pads:
            if pad.GetPadName() == u'35':
                pad1 = pad
            if pad.GetPadName() == u'36':
                pad2 = pad
        pass
        swap(board, pad1, pad2)


# for testing purposes only
if __name__ == "__main__":
    file_handler = logging.FileHandler(filename='swap_pins.log')
    stdout_handler = logging.StreamHandler(sys.stdout)
    handlers = [file_handler, stdout_handler]
    # handlers = [file_handler]

    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(name)s %(lineno)d:%(message)s',
                        datefmt='%m-%d %H:%M:%S',
                        handlers=handlers,
                        filemode='w'
                        )

    logger = logging.getLogger(__name__)
    logger.info("Swap pins plugin started in standalone mode")

    main()

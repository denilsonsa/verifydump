import logging
import os
import pathlib
import re
import subprocess
import sys
import tempfile


class ConversionException(Exception):
    pass


def convert_dump_to_normalized_redump_dump_folder(dump_file_path: pathlib.Path, redump_dump_folder: pathlib.Path, system: str, show_command_output: bool) -> bool:
    """
    Convert a dump file to Redump format in the specified folder, normalizing it to match the Redump conventions for the given system if applicable and possible.

    Returns True if the dump was normalized, or False if we don't know how to normalize dumps for the given system. If we do know how to normalize for the given system but normalization fails for some reason, then an exception will be raised.
    """

    cue_file_path = pathlib.Path(redump_dump_folder, dump_file_path.stem + ".cue")

    dump_suffix_lower = dump_file_path.suffix.lower()

    if dump_suffix_lower == ".chd":
        convert_chd_to_bincue(dump_file_path, cue_file_path, show_command_output)
    else:
        raise ConversionException(f"{pathlib.Path(sys.argv[0]).stem} doesn't know how to handle '{dump_suffix_lower}' dumps")

    return normalize_redump_bincue_dump_for_system(cue_file_path, system)


def convert_chd_to_bincue(chd_file_path: pathlib.Path, output_cue_file_path: pathlib.Path, show_command_output: bool):
    stdout_option = None if show_command_output else subprocess.DEVNULL

    # Use another temporary directory for the chdman output files to keep those separate from the binmerge output files:
    with tempfile.TemporaryDirectory() as chdman_output_folder_path_name:
        chdman_cue_file_path = pathlib.Path(chdman_output_folder_path_name, output_cue_file_path.name)
        logging.debug(f'Converting "{chd_file_path.name}" to .bin/.cue format')
        subprocess.run(["chdman", "extractcd", "--input", str(chd_file_path), "--output", str(chdman_cue_file_path)], check=True, stdout=stdout_option)
        logging.debug(f'Splitting "{output_cue_file_path.name}" into separate tracks if necessary')
        subprocess.run(["binmerge", "--split", "-o", str(output_cue_file_path.parent), str(chdman_cue_file_path), chdman_cue_file_path.stem], check=True, stdout=stdout_option)


def normalize_redump_bincue_dump_for_system(cue_file_path: pathlib.Path, system: str) -> bool:
    dump_path = cue_file_path.parent
    dump_name = cue_file_path.stem

    has_multiple_tracks = len(list(dump_path.glob(f"{dump_name} (Track *).bin"))) > 1
    if not has_multiple_tracks:
        original_bin_name = f"{dump_name} (Track 1).bin"
        single_track_bin_name = f"{dump_name}.bin"

        logging.debug(f"Renaming '{original_bin_name}' to '{single_track_bin_name}' because there is only one .bin file in the dump")

        os.rename(
            pathlib.Path(dump_path, original_bin_name),
            pathlib.Path(dump_path, single_track_bin_name),
        )

        cue_file_path.write_text(cue_file_path.read_text().replace(f'FILE "{original_bin_name}"', f'FILE "{single_track_bin_name}"'))

    is_cue_iso_compatible = not has_multiple_tracks and re.match(r'^\s*FILE\s+"' + re.escape(f"{dump_name}.bin") + r'"\s*BINARY\s+TRACK 01 MODE1/2048\s+INDEX 01 00:00:00\s*$', cue_file_path.read_text())
    if is_cue_iso_compatible:
        logging.debug(f"'{cue_file_path.name}' is .iso compatible so converting dump to .iso and discarding .cue")

        single_track_bin_path = pathlib.Path(dump_path, single_track_bin_name)
        iso_file_path = pathlib.Path(dump_path, f"{dump_name}.iso")

        single_track_bin_path.rename(iso_file_path)
        cue_file_path.unlink()

    system_lower = system.lower() if system else system

    if system_lower in ("Sony - PlayStation".lower(), "psx"):
        return True
    else:
        return False

from abc import ABC, abstractmethod
from distutils.spawn import find_executable
from typing import Tuple, Optional
import subprocess
from subprocess import PIPE, STDOUT
from av1an.project import Project
from chunk import Chunk
from av1an.commandtypes import Command, MPCommands
from av1an_pyo3 import encoder_bin, compose_ffmpeg_pipe


class Encoder(ABC):
    """
    An abstract class used for encoders
    """

    @abstractmethod
    def compose_1_pass(self, a: Project, c: Chunk, output: str) -> MPCommands:
        """
        Composes the commands needed for a 1 pass encode

        :param a: the Project
        :param c: the Chunk
        :param output: path for encoded output
        :return: a MPCommands object (a list of CommandPairs)
        """
        pass

    @abstractmethod
    def compose_2_pass(self, a: Project, c: Chunk, output: str) -> MPCommands:
        """
        Composes the commands needed for a 2 pass encode

        :param a: the Project
        :param c: the Chunk
        :param output: path for encoded output
        :return: a MPCommands object (a list of CommandPairs)
        """
        pass

    @abstractmethod
    def man_q(self, command: Command, q: int) -> Command:
        """Return command with new cq value

        :param command: old command
        :param q: new cq value
        :return: command with new cq value"""
        pass

    @abstractmethod
    def match_line(self, line: str):
        """Extract number of encoded frames from line.

        :param line: one line of text output from the encoder
        :return: match object from re.search matching the number of encoded frames"""
        pass

    def mod_command(self, command, chunk):
        return None

    def make_pipes(
        self,
        a: Project,
        c: Chunk,
        passes: int,
        current_pass: int,
        output: str,
        man_q: int = None,
    ):
        """
        Creates a pipe for the given chunk with the given args

        :param a: the Project
        :param c: the Chunk
        :param passes: the total number of passes (1 or 2)
        :param current_pass: the current_pass
        :param output: path posix string for encoded output
        :param man_q: use a different quality
        :return: a Pipe attached to the encoders stdout
        """
        filter_cmd, enc_cmd = (
            self.compose_1_pass(a, c, output)[0]
            if passes == 1
            else self.compose_2_pass(a, c, output)[current_pass - 1]
        )
        if man_q:
            enc_cmd = self.man_q(enc_cmd, man_q)
        elif c.per_shot_target_quality_cq:
            enc_cmd = self.man_q(enc_cmd, c.per_shot_target_quality_cq)

        ffmpeg_gen_pipe = subprocess.Popen(c.ffmpeg_gen_cmd, stdout=PIPE, stderr=STDOUT)
        ffmpeg_pipe = subprocess.Popen(
            filter_cmd, stdin=ffmpeg_gen_pipe.stdout, stdout=PIPE, stderr=STDOUT
        )
        pipe = subprocess.Popen(
            enc_cmd,
            stdin=ffmpeg_pipe.stdout,
            stdout=PIPE,
            stderr=STDOUT,
            universal_newlines=True,
        )

        utility = (ffmpeg_gen_pipe, ffmpeg_pipe)
        return pipe, utility

    def is_valid(self, project: Project) -> Tuple[bool, Optional[str]]:
        """
        Determines if the encoder is properly set up. Checkes to make sure executable exists and project are all
        compatible with this encoder.
        :param project: the Project
        :return: A tuple of (status, error). Status is false and error is set if encoder is not valid
        """
        if not find_executable(encoder_bin(project.encoder)):
            return (
                False,
                f"Encoder {encoder_bin(project.encoder)} not found. Is it installed in the system path?",
            )
        return True, None

    def __eq__(self, o: object) -> bool:
        """
        Supports equality of encoders based on encoder_bin

        :param o: other object
        :return: True iff o is an EncoderBC and self.encoder_bin == o.encoder_bin
        """
        if not isinstance(o, Encoder):
            return False
        return encoder_bin(o.encoder) == o.encoder_bin

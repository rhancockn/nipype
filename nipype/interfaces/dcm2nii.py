"""The dcm2nii module provides basic functions for dicom conversion

   Change directory to provide relative paths for doctests
   >>> import os
   >>> filepath = os.path.dirname( os.path.realpath( __file__ ) )
   >>> datadir = os.path.realpath(os.path.join(filepath, '../testing/data'))
   >>> os.chdir(datadir)
"""

from nipype.interfaces.base import (CommandLine, CommandLineInputSpec,
                                    InputMultiPath, traits, TraitedSpec,
                                    OutputMultiPath, isdefined,
                                    File, Directory)
import os
from copy import deepcopy
from nipype.utils.filemanip import split_filename
import re

class Dcm2niiInputSpec(CommandLineInputSpec):
    source_names = InputMultiPath(File(exists=True), argstr="%s", position=16,
                                  copyfile=False, mandatory=True)
    anonymize = traits.Bool(True, argstr='-a', usedefault=True, position=0)
    config_file = File(exists=True, argstr="-b %s", genfile=True, position=1)
    collapse_folders = traits.Bool(True, argstr='-c', usedefault=True, position=2)
    date_in_filename = traits.Bool(True, argstr='-d', usedefault=True, position=3)
    events_in_filename = traits.Bool(True, argstr='-e', usedefault=True, position=4)
    source_in_filename = traits.Bool(False, argstr='-f', usedefault=True, position=5)
    gzip_output = traits.Bool(False, argstr='-g', usedefault=True, position=6)
    id_in_filename = traits.Bool(False, argstr='-i', usedefault=True, position=7)
    nii_output = traits.Bool(True, argstr='-n', usedefault=True, position=8)
    output_dir = Directory(exists=True, argstr='-o %s', genfile=True, position=9)
    protocol_in_filename = traits.Bool(True, argstr='-p', usedefault=True, position=10)
    reorient = traits.Bool(argstr='-r', position=11)
    spm_analyze = traits.Bool(argstr='-s', xor=['nii_output'], position=12)
    convert_all_pars = traits.Bool(True, argstr='-v', usedefault=True, position=13)
    reorient_and_crop = traits.Bool(False, argstr='-x', usedefault=True, position=14)
    args = traits.Str(argstr='%s', desc='Additional parameters to the command',
                      position=15)

class Dcm2niiOutputSpec(TraitedSpec):
    converted_files = OutputMultiPath(File(exists=True))
    reoriented_files = OutputMultiPath(File(exists=True))
    reoriented_and_cropped_files = OutputMultiPath(File(exists=True))
    bvecs = OutputMultiPath(File(exists=True))
    bvals = OutputMultiPath(File(exists=True))

class Dcm2nii(CommandLine):
    """Uses MRICRON's dcm2nii to convert dicom files

    Examples
    ========

    >>> from nipype.interfaces.dcm2nii import Dcm2nii
    >>> converter = Dcm2nii()
    >>> converter.inputs.source_names = ['functional_1.dcm', 'functional_2.dcm']
    >>> converter.inputs.gzip_output = True
    >>> converter.inputs.output_dir = '.'
    >>> converter.cmdline #doctest: +ELLIPSIS
    'dcm2nii -a y -b config.ini -c y -d y -e y -f n -g y -i n -n y -o . -p y -v y -x n functional_1.dcm'
    >>> converter.run() # doctest: +SKIP
    """

    input_spec=Dcm2niiInputSpec
    output_spec=Dcm2niiOutputSpec

    _cmd = 'dcm2nii'

    def _format_arg(self, opt, spec, val):
        if opt in ['anonymize', 'collapse_folders', 'date_in_filename', 'events_in_filename',
                   'source_in_filename', 'gzip_output', 'id_in_filename', 'nii_output',
                   'protocol_in_filename', 'reorient', 'spm_analyze', 'convert_all_pars',
                   'reorient_and_crop']:
            spec = deepcopy(spec)
            if val:
                spec.argstr += ' y'
            else:
                spec.argstr += ' n'
                val = True
        if opt == 'source_names':
            return spec.argstr % val[0]
        return super(Dcm2nii, self)._format_arg(opt, spec, val)

    def _run_interface(self, runtime):

        new_runtime = super(Dcm2nii, self)._run_interface(runtime)
        (self.output_files,
         self.reoriented_files,
         self.reoriented_and_cropped_files,
         self.bvecs, self.bvals) = self._parse_stdout(new_runtime.stdout)
        return new_runtime

    def _parse_stdout(self, stdout):
        files = []
        reoriented_files = []
        reoriented_and_cropped_files = []
        bvecs = []
        bvals = []
        skip = False
        last_added_file = None
        for line in stdout.split("\n"):
            if not skip:
                file = None
                if line.startswith("Saving "):
                    file = line[len("Saving "):]
                elif line.startswith("GZip..."):
                    #for gzipped outpus files are not absolute
                    if isdefined(self.inputs.output_dir):
                        output_dir = self.inputs.output_dir
                    else:
                        output_dir = self._gen_filename('output_dir')
                    file = os.path.abspath(os.path.join(output_dir,
                                                        line[len("GZip..."):]))
                elif line.startswith("Number of diffusion directions "):
                    if last_added_file:
                        base, filename, ext = split_filename(last_added_file)
                        bvecs.append(os.path.join(base,filename + ".bvec"))
                        bvals.append(os.path.join(base,filename + ".bval"))
                elif re.search('.*-->(.*)', line):
                    val = re.search('.*-->(.*)', line)
                    val = val.groups()[0]
                    if isdefined(self.inputs.output_dir):
                        output_dir = self.inputs.output_dir
                    else:
                        output_dir = self._gen_filename('output_dir')
                    val = os.path.join(output_dir, val)
                    file = val

                if file:
                    files.append(file)
                    last_added_file = file
                    continue

                if line.startswith("Reorienting as "):
                    reoriented_files.append(line[len("Reorienting as "):])
                    skip = True
                    continue
                elif line.startswith("Cropping NIfTI/Analyze image "):
                    base, filename = os.path.split(line[len("Cropping NIfTI/Analyze image "):])
                    filename = "c" + filename
                    reoriented_and_cropped_files.append(os.path.join(base, filename))
                    skip = True
                    continue
            skip = False
        return files, reoriented_files, reoriented_and_cropped_files, bvecs, bvals

    def _list_outputs(self):
        outputs = self.output_spec().get()
        outputs['converted_files'] = self.output_files
        outputs['reoriented_files'] = self.reoriented_files
        outputs['reoriented_and_cropped_files'] = self.reoriented_and_cropped_files
        outputs['bvecs'] = self.bvecs
        outputs['bvals'] = self.bvals
        return outputs

    def _gen_filename(self, name):
        if name == 'output_dir':
            return os.getcwd()
        elif name == 'config_file':
            config_file = "config.ini"
            f = open(config_file, "w")
            # disable interactive mode
            f.write("[BOOL]\nManualNIfTIConv=0\n")
            f.close()
            return config_file
        return None


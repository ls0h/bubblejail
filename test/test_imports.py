# SPDX-License-Identifier: GPL-3.0-or-later

# Copyright 2019, 2020 igo95862

# This file is part of bubblejail.
# bubblejail is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# bubblejail is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with bubblejail.  If not, see <https://www.gnu.org/licenses/>.


from os import environ
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from unittest import main as unittest_main

from bubblejail.bubblejail_instance import BubblejailInstance
from bubblejail.bubblejail_utils import BubblejailProfile, ImportConfig


class TestImports(IsolatedAsyncioTestCase):
    async def test_imports(self) -> None:
        with TemporaryDirectory() as tempdir:
            real_home = Path(tempdir)
            # Create data dir which is equivalent of XDG_DATA_HOME
            data_dir = real_home / "data"
            data_dir.mkdir()
            # Create test import profile
            dir_to_import = Path('.application')
            test_import_conf = ImportConfig(
                copy=[dir_to_import, ],
            )
            # Test that its not possible to import when there is no data
            self.assertFalse(test_import_conf.available(real_home))
            # Create sample application folder and file
            (real_home / dir_to_import).mkdir()
            test_file_path = dir_to_import / 'test.txt'
            with open(real_home / test_file_path, mode='w') as f:
                f.write('test')
            # Test that now its possible to import
            self.assertTrue(test_import_conf.available(real_home))
            # Set new HOME
            environ['HOME'] = str(real_home)

            BubblejailInstance.DATA_DIR = data_dir

            test_profile = BubblejailProfile(
                import_conf=test_import_conf,
            )

            # Test imports from home
            new_instance = await BubblejailInstance.create_new(
                new_name='test_imports',
                profile=test_profile,
                create_dot_desktop=False,
                do_import_data=True
            )

            self.assertTrue(
                (new_instance.home_bind_path / test_file_path
                 ).exists(),
            )
            with open(new_instance.home_bind_path / test_file_path) as f:
                self.assertEqual('test', f.read())

            # Test imports cross instaces
            new_instance_from_instance = await BubblejailInstance.create_new(
                new_name='test_import_from_instance',
                profile=test_profile,
                do_import_data=True,
                import_from_instance='test_imports'
            )

            self.assertTrue(
                (new_instance_from_instance.home_bind_path / test_file_path
                 ).exists(),
            )
            with open(new_instance_from_instance.home_bind_path /
                      test_file_path) as f:
                self.assertEqual('test', f.read())


if __name__ == '__main__':
    unittest_main()
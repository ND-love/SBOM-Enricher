from app.parsers.debian_packages_parser import parse_debian_packages_text


def test_parse_single_package():
    text = """Package: testpkg
Version: 1.2.3
Architecture: amd64
Section: utils
Filename: pool/main/t/testpkg/testpkg_1.2.3_amd64.deb
Source: testsrc
Depends: libc6 (>= 2.34)
Description: Test package
 Long description line 1
 Long description line 2
"""

    result = parse_debian_packages_text(text)

    assert len(result) == 1
    pkg = result[0]

    assert pkg["package_name"] == "testpkg"
    assert pkg["version"] == "1.2.3"
    assert pkg["architecture"] == "amd64"
    assert pkg["section"] == "utils"
    assert pkg["filename"] == "pool/main/t/testpkg/testpkg_1.2.3_amd64.deb"
    assert pkg["source"] == "testsrc"
    assert pkg["depends"] == "libc6 (>= 2.34)"
    assert pkg["description"] == "Test package\nLong description line 1\nLong description line 2"


def test_parse_multiple_packages():
    text = """Package: pkg1
Version: 1.0
Architecture: amd64
Section: misc
Filename: pool/main/p/pkg1/pkg1_1.0_amd64.deb
Description: Package one

Package: pkg2
Version: 2.0
Architecture: all
Section: admin
Filename: pool/main/p/pkg2/pkg2_2.0_all.deb
Description: Package two
"""

    result = parse_debian_packages_text(text)

    assert len(result) == 2
    assert result[0]["package_name"] == "pkg1"
    assert result[0]["version"] == "1.0"
    assert result[1]["package_name"] == "pkg2"
    assert result[1]["version"] == "2.0"


def test_skip_blocks_without_required_fields():
    text = """Package: broken-only-name
Architecture: amd64
Description: no version here

Version: 1.0
Architecture: amd64
Description: no package name here

Package: valid
Version: 3.1
Architecture: amd64
Description: ok
"""

    result = parse_debian_packages_text(text)

    assert len(result) == 1
    assert result[0]["package_name"] == "valid"
    assert result[0]["version"] == "3.1"
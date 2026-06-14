from __future__ import annotations

SUPPORTED_LANGUAGES = ("python", "cpp")

TEMPLATES = {
    "python": """\
from typing import List


class Solution:
    def solve(self):
        # TODO: implement
        pass
""",
    "cpp": """\
#include <bits/stdc++.h>
using namespace std;

class Solution {
public:
    void solve() {
        // TODO: implement
    }
};
""",
}


def get_template(language: str) -> str:
    language = language.lower()
    if language not in TEMPLATES:
        raise ValueError(f"unsupported language: {language}")
    return TEMPLATES[language]

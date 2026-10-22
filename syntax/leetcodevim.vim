" Readable problem statements without changing the user's editor colorscheme.
if exists('b:current_syntax') && b:current_syntax ==# 'leetcodevim'
  finish
endif
syntax match LeetCodeProblemTitle /\%1l.*/
syntax match LeetCodeSection /^\s*\%(Example\s\+\d\+\|Explanation\|Constraints\|Follow-up\|Hints\).*$/
syntax match LeetCodeInput /\<Input\s*:/
syntax match LeetCodeOutput /\<Output\s*:/
syntax match LeetCodeNumber /\%([[:alnum:]_]\)\@<!-\?\d\+\%(\.\d\+\)\?/
syntax match LeetCodeOperator /<=\|>=\|==\|!=\|[-+*%=<>]/
syntax match LeetCodePunctuation /[\[\]{}(),]/
syntax region LeetCodeString start=/"/ skip=/\\./ end=/"/ oneline
syntax region LeetCodeInline start=/`/ end=/`/ oneline
syntax match LeetCodeLink /https\?:\/\/[^ ]\+/
syntax match LeetCodeCommand /:LeetCode\w\+/
syntax match LeetCodeNavigation /F2: Problems\|\[F2 Problems\]/
syntax match LeetCodeEasy /\[Easy\]/
syntax match LeetCodeMedium /\[Medium\]/
syntax match LeetCodeHard /\[Hard\]/
highlight default LeetCodeProblemTitle gui=bold cterm=bold guifg=#7dd3fc ctermfg=117
highlight default LeetCodeSection gui=bold cterm=bold guifg=#fbbf24 ctermfg=221
highlight default LeetCodeInput gui=bold cterm=bold guifg=#67e8f9 ctermfg=87
highlight default LeetCodeOutput gui=bold cterm=bold guifg=#86efac ctermfg=120
highlight default LeetCodeNumber guifg=#f9a8d4 ctermfg=218
highlight default LeetCodeOperator guifg=#c4b5fd ctermfg=183
highlight default LeetCodePunctuation guifg=#94a3b8 ctermfg=110
highlight default LeetCodeString guifg=#86efac ctermfg=120
highlight default LeetCodeInline guifg=#7dd3fc ctermfg=117
highlight default LeetCodeIdentifier guifg=#7dd3fc ctermfg=117
highlight default LeetCodeLink gui=underline cterm=underline guifg=#93c5fd ctermfg=111
highlight default LeetCodeCommand guifg=#c4b5fd ctermfg=183
highlight default LeetCodeNavigation gui=bold cterm=bold guifg=#7dd3fc ctermfg=117
highlight default LeetCodeShortcut gui=bold cterm=bold guifg=#0f172a guibg=#7dd3fc ctermfg=17 ctermbg=117
let b:current_syntax = 'leetcodevim'

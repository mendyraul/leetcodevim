if exists('g:loaded_leetcodevim')
  finish
endif
let g:loaded_leetcodevim = 1

function! s:LeetCodeInit(workspace, language) abort
  let l:cmd = 'leetcodevim init --workspace ' . shellescape(a:workspace)
  let l:cmd .= ' --language ' . shellescape(a:language)
  echo system(l:cmd)
endfunction

function! s:LeetCodePull(slug) abort
  let l:cmd = 'leetcodevim pull ' . shellescape(a:slug)
  let l:path = system(l:cmd)
  execute 'edit ' . fnameescape(trim(l:path))
endfunction

function! s:LeetCodeList() abort
  let l:items = systemlist('leetcodevim list')
  if empty(l:items)
    echo 'No local problems found.'
    return
  endif
  let l:choices = ['Select a problem:']
  for l:item in l:items
    let l:parts = split(l:item, "\t")
    call add(l:choices, l:parts[0])
  endfor
  let l:idx = inputlist(l:choices)
  if l:idx <= 0
    return
  endif
  let l:selected = l:items[l:idx - 1]
  let l:path = split(l:selected, "\t")[1]
  execute 'edit ' . fnameescape(l:path)
endfunction

function! s:LeetCodeListFzf() abort
  if !exists('*fzf#run')
    echo 'fzf.vim not detected.'
    return
  endif
  let l:items = systemlist('leetcodevim list')
  if empty(l:items)
    echo 'No local problems found.'
    return
  endif
  call fzf#run(fzf#wrap({
        \ 'source': l:items,
        \ 'sink': function('s:LeetCodeOpenFromLine'),
        \ 'options': '--with-nth=1 --delimiter=\t --prompt="LeetCode> "',
        \ }))
endfunction

function! s:LeetCodeOpenFromLine(line) abort
  if empty(a:line)
    return
  endif
  let l:path = split(a:line, "\t")[1]
  execute 'edit ' . fnameescape(l:path)
endfunction

function! s:LeetCodeListTelescope() abort
  if !has('nvim') || !exists(':Telescope')
    echo 'telescope.nvim not detected.'
    return
  endif
  let l:items = systemlist('leetcodevim list')
  if empty(l:items)
    echo 'No local problems found.'
    return
  endif
  lua << EOF
local ok, pickers = pcall(require, "telescope.pickers")
if not ok then
  vim.notify("telescope.nvim not available", vim.log.levels.WARN)
  return
end
local finders = require("telescope.finders")
local conf = require("telescope.config").values
local actions = require("telescope.actions")
local action_state = require("telescope.actions.state")

local lines = vim.fn.systemlist("leetcodevim list")
local results = {}
for _, line in ipairs(lines) do
  local slug, path = line:match("^(.-)\t(.*)$")
  if slug and path then
    table.insert(results, { display = slug, path = path })
  end
end

pickers.new({}, {
  prompt_title = "LeetCode Problems",
  finder = finders.new_table({
    results = results,
    entry_maker = function(entry)
      return {
        value = entry,
        display = entry.display,
        ordinal = entry.display,
      }
    end,
  }),
  sorter = conf.generic_sorter({}),
  attach_mappings = function(prompt_bufnr)
    actions.select_default:replace(function()
      local selection = action_state.get_selected_entry()
      actions.close(prompt_bufnr)
      if selection and selection.value and selection.value.path then
        vim.cmd("edit " .. vim.fn.fnameescape(selection.value.path))
      end
    end)
    return true
  end,
}):find()
EOF
endfunction


function! s:LeetCodeRecent() abort
  let l:path = trim(system('leetcodevim recent'))
  if empty(l:path)
    echo 'No local problems found.'
    return
  endif
  execute 'edit ' . fnameescape(l:path)
endfunction

function! s:LeetCodeNext() abort
  let l:path = trim(system('leetcodevim next'))
  if empty(l:path)
    echo 'No template-only problems found.'
    return
  endif
  execute 'edit ' . fnameescape(l:path)
endfunction

function! s:LeetCodeStatus() abort
  echo join(systemlist('leetcodevim status'), " | ")
endfunction

function! s:LeetCodeListSmart() abort
  if has('nvim') && exists(':Telescope')
    call s:LeetCodeListTelescope()
    return
  endif
  if exists('*fzf#run')
    call s:LeetCodeListFzf()
    return
  endif
  call s:LeetCodeList()
endfunction

command! -nargs=+ LeetCodeInit call s:LeetCodeInit(<f-args>)
command! -nargs=1 LeetCodePull call s:LeetCodePull(<f-args>)
command! LeetCodeList call s:LeetCodeList()
command! LeetCodeListFzf call s:LeetCodeListFzf()
command! LeetCodeListTelescope call s:LeetCodeListTelescope()
command! LeetCodeListSmart call s:LeetCodeListSmart()
command! LeetCodeRecent call s:LeetCodeRecent()
command! LeetCodeNext call s:LeetCodeNext()
command! LeetCodeStatus call s:LeetCodeStatus()

let s:save_cpo = &cpo
set cpo&vim
let s:job = v:null
let s:running = 0
let s:sequence = 0
let s:pending = {}
let s:generation = 0
let s:windows = {}
let s:buffers = {}
let s:slug = ''
let s:language = get(g:, 'leetcodevim_language', '')
let s:problem = {}
let s:search = ''
let s:offset = 0
let s:filters = {'difficulty': '', 'topic': '', 'status': ''}
let s:lasturl = ''
let s:remote_id = ''
let s:editor_buffer = -1
let s:source_window = 0
let s:menu = ['LeetCode', '[Search / filters]', '[Daily question]', '[Random question]', '[Local problems]', '[Profile]', '[Study plans]', '[Contests]', '[Favorites]', '[Login]', '']

function! s:exists() abort
  return !empty(s:windows) && win_id2tabwin(get(s:windows, 'editor', 0))[0] > 0
endfunction

function! s:start() abort
  if s:running
    return 1
  endif
  let l:argv = get(g:, 'leetcodevim_command', ['leetcodevim'])
  if type(l:argv) == v:t_string
    let l:argv = [l:argv]
  endif
  if !executable(l:argv[0])
    echoerr 'leetcodevim not found. Install the CLI or set g:leetcodevim_command to its executable path.'
    return 0
  endif
  let l:argv = l:argv + ['serve', '--stdio']
  if has('nvim')
    let s:running = luaeval("require('leetcodevim.transport').start(_A)", l:argv)
  elseif has('job') && has('channel')
    let s:job = job_start(l:argv, {'out_mode': 'nl', 'out_cb': function('s:output'), 'exit_cb': function('s:exit'), 'err_io': 'null'})
    let s:running = job_status(s:job) ==# 'run'
  else
    echoerr 'LeetCodeVim requires Vim with +job/+channel or Neovim.'
  endif
  return s:running
endfunction

function! s:output(channel, line) abort
  call leetcodevim#receive(a:line)
endfunction
function! s:exit(job, status) abort
  call leetcodevim#disconnected()
endfunction
function! leetcodevim#disconnected() abort
  let s:running = 0
  let s:pending = {}
  if s:exists()
    call s:render('results', ['Backend stopped. Run an action to restart it.', 'Session-only credentials must be entered again.'])
  endif
endfunction

function! s:send(value) abort
  let l:line = json_encode(a:value) . "\n"
  if has('nvim')
    call luaeval("require('leetcodevim.transport').send(_A)", l:line)
  else
    call ch_sendraw(job_getchannel(s:job), l:line)
  endif
endfunction

function! s:request(method, params, callback) abort
  if !s:start()
    return
  endif
  let s:sequence += 1
  let l:id = s:sequence
  let s:pending[string(l:id)] = {'callback': a:callback, 'generation': s:generation}
  call s:send({'v': 1, 'id': l:id, 'method': a:method, 'params': a:params})
  if s:exists()
    call s:render('results', ['Loading ' . a:method . '...', ':LeetCodeCancel stops pending work.'])
  endif
endfunction

function! leetcodevim#receive(line) abort
  try
    let l:response = json_decode(a:line)
  catch
    return
  endtry
  let l:key = string(get(l:response, 'id', -1))
  if !has_key(s:pending, l:key)
    return
  endif
  let l:pending = s:pending[l:key]
  if l:pending.generation != s:generation
    if has_key(l:response, 'result') || has_key(l:response, 'error')
      call remove(s:pending, l:key)
    endif
    return
  endif
  if has_key(l:response, 'error')
    call remove(s:pending, l:key)
    call s:render('results', ['Error: ' . get(l:response.error, 'message', 'Request failed.')])
  elseif has_key(l:response, 'result')
    call remove(s:pending, l:key)
    call call(l:pending.callback, [l:response.result])
  elseif get(l:response, 'event', '') ==# 'operation'
    let s:remote_id = l:response.remote_id
    call s:render('results', [get(l:response, 'message', ''), 'Remote ID: ' . s:remote_id])
  endif
endfunction

function! s:scratch(name) abort
  let l:existing = bufnr('^LeetCode-' . a:name . '$')
  if l:existing > 0
    execute 'silent keepalt buffer ' . l:existing
  else
    execute 'silent keepalt enew'
    execute 'silent file LeetCode-' . a:name
  endif
  setlocal buftype=nofile bufhidden=hide noswapfile nobuflisted nowrap nonumber norelativenumber
  setlocal signcolumn=no
  let b:leetcodevim_view = a:name
  let s:buffers[a:name] = bufnr('%')
  highlight default link LeetCodeEasy String
  highlight default link LeetCodeMedium Type
  highlight default link LeetCodeHard ErrorMsg
  highlight default link LeetCodeHeading Title
  syntax match LeetCodeEasy /\[Easy\]/
  syntax match LeetCodeMedium /\[Medium\]/
  syntax match LeetCodeHard /\[Hard\]/
  syntax match LeetCodeHeading /^\[.*\]$/
  runtime! syntax/leetcodevim.vim
  nnoremap <silent><buffer> <F2> :LeetCodeBrowser<CR>
  let &l:statusline = '%<%f %m%=%#LeetCodeShortcut# [F2 Problems] %*'
  nnoremap <silent><buffer> ? :call leetcodevim#help()<CR>
  nnoremap <silent><buffer> q :LeetCodeClose<CR>
  nnoremap <silent><buffer> o :call leetcodevim#browser()<CR>
  nnoremap <silent><buffer> <CR> :call leetcodevim#link()<CR>
endfunction

function! s:browser_width() abort
  return min([max([24, get(g:, 'leetcodevim_browser_width', 52)]), max([24, &columns * 45 / 100])])
endfunction

function! s:ensure() abort
  if s:exists()
    call win_gotoid(s:windows.editor)
    return
  endif
  let s:source_window = win_getid()
  tabnew
  let t:leetcodevim_workspace = 1
  let s:windows = {}
  let s:editor_buffer = -1
  call s:scratch('editor')
  let s:windows.editor = win_getid()
  execute 'leftabove ' . s:browser_width() . 'vsplit'
  call s:scratch('browser')
  let s:windows.browser = win_getid()
  let b:leetcodevim_entries = {}
  nnoremap <silent><buffer> <CR> :call leetcodevim#select()<CR>
  nnoremap <silent><buffer> / :call leetcodevim#search()<CR>
  nnoremap <silent><buffer> f :call leetcodevim#filters()<CR>
  nnoremap <silent><buffer> r :call leetcodevim#refresh()<CR>
  nnoremap <silent><buffer> ] :call leetcodevim#page(1)<CR>
  nnoremap <silent><buffer> [ :call leetcodevim#page(-1)<CR>
  setlocal winfixwidth
  call win_gotoid(s:windows.editor)
  leftabove vsplit
  call s:scratch('description')
  setlocal wrap linebreak
  let s:windows.description = win_getid()
  call win_gotoid(s:windows.editor)
  botright 10split
  call s:scratch('results')
  setlocal wrap linebreak
  let s:windows.results = win_getid()
  nnoremap <silent><buffer> p :call leetcodevim#resume()<CR>
  call s:render('browser', s:menu + ['Loading catalog...'])
  call s:render('description', ['Select a problem.', '', 'Description | Code | Hints | Editorial | Discussion | Submissions', '', ':LeetCodeHints  :LeetCodeEditorial  :LeetCodeDiscuss', ':LeetCodeHistory  :LeetCodeCases', '', 'Use :LeetCodeLanguage cpp or python to switch drafts.'])
  call s:render('results', ['Local test: :LeetCodeTest', 'Remote run: :LeetCodeRun', 'Official judge: :LeetCodeSubmit', '? displays all commands.'])
  call win_gotoid(s:windows.browser)
  augroup leetcodevim_layout
    autocmd!
    autocmd VimResized * call leetcodevim#resize()
  augroup END
  call leetcodevim#resize()
endfunction

function! s:render(view, lines) abort
  let l:buffer = get(s:buffers, a:view, -1)
  if l:buffer < 0 || !bufexists(l:buffer)
    return
  endif
  call setbufvar(l:buffer, '&modifiable', 1)
  call setbufline(l:buffer, 1, empty(a:lines) ? ['(empty)'] : a:lines)
  if len(getbufline(l:buffer, 1, '$')) > len(a:lines)
    call deletebufline(l:buffer, len(a:lines) + 1, '$')
  endif
  call setbufvar(l:buffer, '&modifiable', 0)
endfunction

function! s:display(result) abort
  let s:lasturl = get(a:result, 'url', '')
  let l:lines = []
  if has_key(a:result, 'message')
    call add(l:lines, a:result.message)
  endif
  if get(a:result, 'mode', '') ==# 'browser'
    call extend(l:lines, ['', 'Browser feature: ' . s:lasturl, 'Press o to open in your browser.'])
  endif
  if get(a:result, 'stale', 0)
    call add(l:lines, 'Cached content from ' . get(a:result, 'updated_at', '') . '; refresh to check for changes.')
  endif
  if has_key(a:result, 'entries')
    let l:links = {}
    for l:entry in a:result.entries
      call add(l:lines, l:entry.title)
      let l:links[len(l:lines)] = l:entry.url
    endfor
    call add(l:lines, 'Select an entry with Enter to open it in your browser.')
    call s:render('results', l:lines)
    call setbufvar(s:buffers.results, 'leetcodevim_links', l:links)
  elseif has_key(a:result, 'text')
    call extend(l:lines, split(a:result.text, "\n", 1))
    call s:render('description', l:lines)
  else
    call extend(l:lines, get(a:result, 'lines', s:pretty(a:result)))
    call s:render('results', l:lines)
  endif
endfunction

function! s:pretty(value) abort
  if type(a:value) == v:t_dict && has_key(a:value, 'results')
    let l:lines = [get(a:value, 'passed', 0) ? 'All local cases passed.' : 'Local cases failed.']
    for l:case in a:value.results
      call add(l:lines, printf('Case %d: %s', l:case.index, l:case.passed ? 'PASS' : 'FAIL'))
      call add(l:lines, 'Expected: ' . json_encode(l:case.expected))
      call add(l:lines, 'Actual:   ' . json_encode(l:case.actual))
      if !empty(get(l:case, 'stdout', ''))
        call add(l:lines, 'stdout: ' . l:case.stdout)
      endif
      if !empty(get(l:case, 'stderr', ''))
        call add(l:lines, 'stderr: ' . l:case.stderr)
      endif
    endfor
    return l:lines
  endif
  return s:tree(a:value, 0)
endfunction

function! s:tree(value, depth) abort
  let l:lines = []
  let l:pad = repeat(' ', a:depth * 2)
  if a:depth > 6 | return [l:pad . '...'] | endif
  if type(a:value) == v:t_dict
    for [l:key, l:value] in items(a:value)
      if type(l:value) == v:t_dict || type(l:value) == v:t_list
        call add(l:lines, l:pad . l:key . ':')
        call extend(l:lines, s:tree(l:value, a:depth + 1))
      else
        call add(l:lines, l:pad . l:key . ': ' . (type(l:value) == v:t_string ? l:value : json_encode(l:value)))
      endif
    endfor
  elseif type(a:value) == v:t_list
    for l:item in a:value[:199]
      call extend(l:lines, s:tree(l:item, a:depth + 1))
      call add(l:lines, '')
    endfor
  else
    call add(l:lines, l:pad . (type(a:value) == v:t_string ? a:value : json_encode(a:value)))
  endif
  return l:lines
endfunction

function! leetcodevim#dashboard() abort
  call s:ensure()
  call leetcodevim#browse('')
endfunction
function! leetcodevim#browse(search) abort
  call s:ensure()
  call leetcodevim#view('browser')
  let s:generation += 1
  let s:search = a:search
  let s:offset = 0
  call s:catalog(0)
endfunction
function! s:catalog(refresh) abort
  let l:params = extend(copy(s:filters), {'search': s:search, 'offset': s:offset, 'limit': 50, 'refresh': a:refresh ? v:true : v:false})
  call s:request('browse', l:params, function('s:catalog_result'))
endfunction
function! s:catalog_result(result) abort
  let l:data = get(a:result, 'data', {})
  let l:lines = copy(s:menu)
  call add(l:lines, printf('Results %d / %d', s:offset, get(l:data, 'total', 0)))
  call add(l:lines, 'Search: ' . s:search . '  [ / search; f filters; [ ] pages ]')
  let l:entries = {}
  for l:item in get(l:data, 'questions', [])
    call add(l:lines, printf('%s %s [%s]%s', get(l:item, 'questionFrontendId', ''), l:item.title,
          \ l:item.difficulty, get(l:item, 'isPaidOnly', 0) ? ' [Premium]' : ''))
    let l:entries[len(l:lines)] = l:item.titleSlug
  endfor
  call s:render('browser', l:lines)
  call setbufvar(s:buffers.browser, 'leetcodevim_entries', l:entries)
  call s:render('results', [get(a:result, 'cached', 0) ? 'Cached catalog; press r to refresh.' : 'Catalog loaded.', get(a:result, 'warning', '')])
endfunction
function! leetcodevim#select() abort
  let l:row = line('.')
  if l:row == 2 | call leetcodevim#search() | return | endif
  if l:row == 3 | call leetcodevim#pick('daily') | return | endif
  if l:row == 4 | call leetcodevim#pick('random') | return | endif
  if l:row == 5 | call leetcodevim#action('local') | return | endif
  if l:row == 6 | call leetcodevim#profile('') | return | endif
  if l:row == 7 | call leetcodevim#action('study') | return | endif
  if l:row == 8 | call leetcodevim#action('contests') | return | endif
  if l:row == 9 | call leetcodevim#action('favorites') | return | endif
  if l:row == 10 | call leetcodevim#login() | return | endif
  let l:slug = get(get(b:, 'leetcodevim_entries', {}), l:row, '')
  if !empty(l:slug)
    call leetcodevim#open(l:slug)
  endif
endfunction
function! leetcodevim#search() abort
  let l:search = input('Search LeetCode: ', s:search)
  call leetcodevim#browse(l:search)
endfunction
function! leetcodevim#filters() abort
  let s:filters.difficulty = input('Difficulty (Easy/Medium/Hard or empty): ', s:filters.difficulty)
  let s:filters.topic = input('Topic slug (array, dynamic-programming, ...): ', s:filters.topic)
  let s:filters.status = input('Status (NOT_STARTED/TRIED/AC or empty): ', s:filters.status)
  let s:offset = 0
  call s:catalog(1)
endfunction
function! leetcodevim#refresh() abort
  call s:catalog(1)
endfunction
function! leetcodevim#page(direction) abort
  let s:offset = max([0, s:offset + a:direction * 50])
  call s:catalog(0)
endfunction

function! s:save() abort
  let l:buffers = [s:editor_buffer]
  for l:info in gettabinfo(tabpagenr())
    for l:win in l:info.windows
      let l:buffer = winbufnr(l:win)
      if getbufvar(l:buffer, '&buftype') ==# '' && index(l:buffers, l:buffer) < 0
        call add(l:buffers, l:buffer)
      endif
    endfor
  endfor
  for l:buffer in l:buffers
    if l:buffer > 0 && bufexists(l:buffer) && getbufvar(l:buffer, '&modified')
      if confirm('Save ' . fnamemodify(bufname(l:buffer), ':t') . ' before continuing?', "&Save\n&Cancel", 2) != 1
        return 0
      endif
      let l:origin = win_getid()
      call win_gotoid(s:windows.editor)
      try
        execute 'silent keepalt buffer ' . l:buffer
        silent update
      catch
        echoerr 'Could not save the file.'
        return 0
      finally
        if s:editor_buffer > 0 && bufexists(s:editor_buffer)
          call win_gotoid(s:windows.editor)
          execute 'silent keepalt buffer ' . s:editor_buffer
        endif
        call win_gotoid(l:origin)
      endtry
    endif
  endfor
  return 1
endfunction
function! leetcodevim#open(slug) abort
  call s:ensure()
  if !s:save()
    return
  endif
  let s:generation += 1
  call s:request('open', {'slug': a:slug, 'language': s:language}, function('s:opened'))
endfunction
function! s:opened(result) abort
  let s:slug = a:result.slug
  let s:problem = a:result
  let s:language = a:result.language
  let s:lasturl = a:result.url
  call s:render('description', [a:result.problem.title . ' [' . a:result.problem.difficulty . ']', '',
        \ 'F2: Problems | :LeetCodeBrowser to choose another question', '',
        \ 'Hints: :LeetCodeHints | Editorial: :LeetCodeEditorial',
        \ 'Discussion: :LeetCodeDiscuss | History: :LeetCodeHistory', ''] + split(a:result.description, "\n", 1))
  call win_gotoid(s:windows.editor)
  execute 'edit ' . fnameescape(a:result.path)
  let s:editor_buffer = bufnr('%')
  setlocal bufhidden=hide
  nnoremap <silent><buffer> <F2> :LeetCodeBrowser<CR>
  inoremap <silent><buffer> <F2> <Esc>:LeetCodeBrowser<CR>
  let &l:statusline = '%<%f %m%=%#LeetCodeShortcut# [F2 Problems] %*'
  nnoremap <silent><buffer> <localleader>lt :LeetCodeTest<CR>
  nnoremap <silent><buffer> <localleader>lr :LeetCodeRun<CR>
  nnoremap <silent><buffer> <localleader>ls :LeetCodeSubmit<CR>
  call s:render('results', ['Opened ' . s:slug . ' (' . s:language . ').',
        \ 'F2: Problems — reopen the question browser.  :LeetCodeCases edits test cases.'])
  let l:browser = get(s:windows, 'browser', 0)
  if win_id2tabwin(l:browser)[0] == tabpagenr()
    call win_execute(l:browser, 'hide')
  endif
  let l:description = get(s:windows, 'description', 0)
  if win_id2tabwin(l:description)[0] == tabpagenr()
    call win_execute(l:description, 'vertical resize ' . (&columns * 45 / 100))
    let l:names = filter(copy(get(a:result.problem, 'parameter_names', [])), 'v:val =~# "^[A-Za-z_][A-Za-z0-9_]*$"')
    if !empty(l:names)
      call win_execute(l:description, 'syntax clear LeetCodeIdentifier')
      call win_execute(l:description, 'syntax keyword LeetCodeIdentifier ' . join(l:names))
    endif
  endif
  call leetcodevim#resize()
endfunction
function! leetcodevim#language(language) abort
  if index(['python', 'cpp'], a:language) < 0
    echoerr 'Choose python or cpp.'
    return
  endif
  if !s:save() | return | endif
  let s:language = a:language
  if !empty(s:slug) | call leetcodevim#open(s:slug) | endif
endfunction
function! leetcodevim#execute(method, slug) abort
  call s:ensure()
  let l:slug = empty(a:slug) ? s:slug : a:slug
  if empty(l:slug)
    echoerr 'Open a problem first.'
    return
  endif
  if !s:save() | return | endif
  if a:method ==# 'submit' && confirm('Submit ' . l:slug . ' (' . s:language . ') to LeetCode?', "&Submit\n&Cancel", 2) != 1
    return
  endif
  call s:request(a:method, {'slug': l:slug, 'language': s:language, 'confirmed': a:method ==# 'submit' ? v:true : v:false}, function('s:display'))
endfunction
function! leetcodevim#action(method) abort
  call s:ensure()
  if a:method ==# 'auth.logout'
    call leetcodevim#cancel()
    let s:generation += 1
    let s:problem = {}
    let s:remote_id = ''
    call s:render('browser', s:menu + ['Signed out. Refresh the catalog to browse anonymously.'])
    call setbufvar(s:buffers.browser, 'leetcodevim_entries', {})
    call s:render('description', ['Signed out. Local solutions and notes are retained.'])
  endif
  call s:request(a:method, {'slug': s:slug, 'language': s:language},
        \ index(['cases', 'notes', 'compose'], a:method) >= 0 ? function('s:cases') :
        \ a:method ==# 'favorites' ? function('s:favorites') :
        \ index(['local', 'recent'], a:method) >= 0 ? function('s:local') : function('s:display'))
endfunction
function! s:favorites(result) abort
  call s:local(a:result)
  call s:display(a:result)
endfunction
function! leetcodevim#unfavorite() abort
  call s:ensure()
  call s:request('favorite', {'slug': s:slug, 'favorite': v:false}, function('s:display'))
endfunction
function! s:cases(result) abort
  call win_gotoid(s:windows.results)
  split
  execute 'edit ' . fnameescape(a:result.path)
  let &l:filetype = a:result.language
  setlocal bufhidden=hide
  let s:lasturl = get(a:result, 'url', s:lasturl)
  if !empty(get(a:result, 'message', '')) | echo a:result.message | endif
endfunction
function! leetcodevim#status(slug) abort
  call s:ensure()
  call s:request('status', {'slug': a:slug}, function('s:display'))
endfunction
function! leetcodevim#mark(status) abort
  call s:ensure()
  if empty(s:slug) | echoerr 'Open a problem first.' | return | endif
  let l:status = empty(a:status) ? input('Status (in-progress/tested/solved/review): ', 'in-progress') : a:status
  call s:request('mark', {'slug': s:slug, 'status': l:status}, function('s:display'))
endfunction
function! leetcodevim#poll(remote_id) abort
  call s:ensure()
  let s:remote_id = a:remote_id
  call s:request('poll', {'remote_id': a:remote_id}, function('s:display'))
endfunction
function! leetcodevim#restore(remote_id) abort
  call s:ensure()
  if !s:save() | return | endif
  if confirm('Restore submission ' . a:remote_id . '? The existing file will be backed up.', "&Restore\n&Cancel", 2) != 1
    return
  endif
  call s:request('restore', {'remote_id': a:remote_id, 'slug': s:slug, 'confirmed': v:true}, function('s:restored'))
endfunction
function! s:restored(result) abort
  call s:display(a:result)
  let l:buf = bufnr(a:result.path)
  if l:buf > 0 && !getbufvar(l:buf, '&modified') && s:exists()
    call win_gotoid(s:windows.editor)
    execute 'edit ' . fnameescape(a:result.path)
    let s:editor_buffer = bufnr('%')
    let s:language = a:result.language
    let s:slug = a:result.slug
  endif
endfunction
function! s:local(result) abort
  let l:lines = copy(s:menu)
  let l:entries = {}
  for l:item in a:result.data
    call add(l:lines, l:item.slug . ' [' . l:item.status . ']')
    let l:entries[len(l:lines)] = l:item.slug
  endfor
  call s:render('browser', l:lines)
  call setbufvar(s:buffers.browser, 'leetcodevim_entries', l:entries)
endfunction
function! leetcodevim#next() abort
  call s:ensure()
  call s:request('local', {}, function('s:next'))
endfunction
function! s:next(result) abort
  for l:item in a:result.data
    if index(['solved', 'submitted'], l:item.status) < 0
      call leetcodevim#open(l:item.slug)
      return
    endif
  endfor
  call s:render('results', ['No unsolved local problems.'])
endfunction
function! leetcodevim#profile(username) abort
  call s:ensure()
  call s:request('profile', {'username': a:username}, function('s:display'))
endfunction
function! leetcodevim#pick(method) abort
  call s:ensure()
  call s:request(a:method, {}, function('s:picked'))
endfunction
function! s:picked(result) abort
  let l:value = a:result.data
  call leetcodevim#open(has_key(l:value, 'question') ? l:value.question.titleSlug : l:value.titleSlug)
endfunction
function! leetcodevim#login() abort
  call s:ensure()
  let l:choice = inputlist(['LeetCode login:', '1. Open sign-in in browser', '2. Import browser cookies', '3. Enter cookies (hidden)', '4. Verify current session'])
  if l:choice == 1
    let s:lasturl = 'https://leetcode.com/accounts/login/'
    call leetcodevim#browser()
  elseif l:choice == 2
    call s:request('auth.import', {'browser': input('Browser (chrome/brave/firefox/edge/chromium): ', 'chrome')}, function('s:auth_result'))
  elseif l:choice == 3
    let l:session = inputsecret('LEETCODE_SESSION: ')
    let l:csrf = inputsecret('csrftoken: ')
    call s:request('auth.set', {'session': l:session, 'csrf': l:csrf}, function('s:auth_result'))
    let l:session = ''
    let l:csrf = ''
  elseif l:choice == 4
    call s:request('auth.status', {}, function('s:display'))
  endif
endfunction
function! s:auth_result(result) abort
  let s:generation += 1
  let s:problem = {}
  let s:remote_id = ''
  call s:render('browser', s:menu + ['Account changed. Refresh the catalog.'])
  call setbufvar(s:buffers.browser, 'leetcodevim_entries', {})
  call s:render('description', ['Account verified. Reopen the problem to refresh account-specific content.'])
  call s:display(a:result)
endfunction
function! leetcodevim#hints() abort
  let l:lines = ['Hints (spoilers)', '']
  for l:hint in get(s:problem, 'hints', [])
    call add(l:lines, substitute(l:hint, '<[^>]*>', '', 'g'))
    call add(l:lines, '')
  endfor
  if len(l:lines) == 2 | call add(l:lines, 'No hints available.') | endif
  call s:render('description', l:lines)
endfunction
function! leetcodevim#resume() abort
  if !empty(s:remote_id)
    call s:request('poll', {'remote_id': s:remote_id}, function('s:display'))
  endif
endfunction
function! leetcodevim#cancel() abort
  for l:id in keys(copy(s:pending))
    let s:sequence += 1
    call s:send({'v': 1, 'id': s:sequence, 'method': 'cancel', 'params': {'id': str2nr(l:id)}})
  endfor
endfunction
function! leetcodevim#browser() abort
  if s:lasturl !~# '^https://leetcode\.com/'
    echoerr 'No LeetCode browser link selected.'
    return
  endif
  if confirm('Open ' . s:lasturl . ' in your browser?', "&Open\n&Cancel", 2) != 1 | return | endif
  if has('mac')
    let l:cmd = ['open', s:lasturl]
  elseif has('win32')
    let l:cmd = ['rundll32', 'url.dll,FileProtocolHandler', s:lasturl]
  else
    let l:cmd = ['xdg-open', s:lasturl]
  endif
  if has('nvim') | call jobstart(l:cmd, {'detach': v:true}) | else | call job_start(l:cmd) | endif
endfunction
function! leetcodevim#link() abort
  let l:url = get(get(b:, 'leetcodevim_links', {}), line('.'), '')
  if !empty(l:url)
    let s:lasturl = l:url
    call leetcodevim#browser()
  endif
endfunction
function! leetcodevim#resize() abort
  if !s:exists() || !get(t:, 'leetcodevim_workspace', 0) | return | endif
  for l:view in ['browser', 'description']
    let l:win = get(s:windows, l:view, 0)
    if win_id2tabwin(l:win)[0] == tabpagenr() && &columns < (l:view ==# 'browser' ? 100 : 75)
      call win_execute(l:win, 'hide')
    endif
  endfor
  let l:browser = get(s:windows, 'browser', 0)
  if win_id2tabwin(l:browser)[0] == tabpagenr()
    call win_execute(l:browser, 'vertical resize ' . s:browser_width())
  endif
endfunction
function! leetcodevim#view(view) abort
  call s:ensure()
  if a:view ==# 'code'
    if s:editor_buffer > 0
      call win_gotoid(s:windows.editor)
      execute 'buffer ' . s:editor_buffer
    endif
    return
  endif
  if !has_key(s:buffers, a:view) | return | endif
  let l:win = get(s:windows, a:view, 0)
  if win_id2tabwin(l:win)[0] > 0
    call win_gotoid(l:win)
  else
    call win_gotoid(s:windows.editor)
    if a:view ==# 'browser' || a:view ==# 'description'
      leftabove vsplit
    else
      botright 10split
    endif
    execute 'buffer ' . s:buffers[a:view]
    let s:windows[a:view] = win_getid()
  endif
  if a:view ==# 'browser'
    wincmd H
    execute 'vertical resize ' . s:browser_width()
    setlocal winfixwidth
  endif
endfunction
function! leetcodevim#close() abort
  if !s:exists() | return | endif
  if !s:save() | return | endif
  call leetcodevim#cancel()
  let s:generation += 1
  call win_gotoid(s:windows.editor)
  tabclose
  let s:windows = {}
  if s:source_window | call win_gotoid(s:source_window) | endif
endfunction
function! leetcodevim#help() abort
  call s:render('results', [':LeetCodeBrowse [query] | :LeetCodeOpen slug | :LeetCodeDaily | :LeetCodeRandom',
        \ ':LeetCodeLanguage python/cpp | :LeetCodeCases | :LeetCodeTest | :LeetCodeRun | :LeetCodeSubmit',
        \ ':LeetCodeHints | :LeetCodeEditorial | :LeetCodeDiscuss | :LeetCodeHistory',
        \ ':LeetCodeProfile | :LeetCodeStudy | :LeetCodeContests | :LeetCodeFavorites',
        \ ':LeetCodeLogin | :LeetCodeLogout | :LeetCodeDoctor | :LeetCodeCancel | :LeetCodeClose',
        \ 'Browser: / search, f filters, [ ] pages, Enter select, r refresh, o open selected feature website.',
        \ 'Results: p resumes the most recent remote operation.'])
endfunction
function! leetcodevim#init(workspace, language) abort
  let l:cmd = get(g:, 'leetcodevim_command', ['leetcodevim'])
  if type(l:cmd) == v:t_string | let l:cmd = [l:cmd] | endif
  let l:cmd += ['init', '--workspace', expand(a:workspace), '--language', a:language]
  echo system(join(map(l:cmd, 'shellescape(v:val)'), ' '))
endfunction

let &cpo = s:save_cpo
unlet s:save_cpo

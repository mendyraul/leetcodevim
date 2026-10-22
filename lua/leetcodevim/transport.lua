-- Neovim process adapter. The workspace and protocol are shared with Vim.
local M = {}
local job
local remainder = ''
function M.start(argv)
  remainder = ''
  job = vim.fn.jobstart(argv, {
    on_stdout = function(_, chunks)
      if not chunks then return end
      chunks[1] = remainder .. chunks[1]
      remainder = chunks[#chunks]
      for i = 1, #chunks - 1 do
        local line = chunks[i]
        if line ~= '' then vim.fn['leetcodevim#receive'](line) end
      end
    end,
    on_exit = function() job = nil; vim.fn['leetcodevim#disconnected']() end,
  })
  return job > 0
end
function M.send(line)
  if job then vim.fn.chansend(job, line) end
end
function M.stop()
  if job then vim.fn.jobstop(job); job = nil end
end
return M

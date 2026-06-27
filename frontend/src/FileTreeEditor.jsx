import { useState } from 'react'

function buildTree(paths) {
  const root = []
  for (const path of paths) {
    const isDir = path.endsWith('/')
    const segments = path.replace(/\/$/, '').split('/').filter(Boolean)
    let level = root
    segments.forEach((seg, idx) => {
      const isLast = idx === segments.length - 1
      let node = level.find((n) => n.name === seg)
      if (!node) {
        node = { _key: crypto.randomUUID(), name: seg, isDir: !isLast || isDir, children: [] }
        level.push(node)
      }
      level = node.children
    })
  }
  return root
}

function flattenTree(nodes, prefix = '') {
  const paths = []
  for (const node of nodes) {
    paths.push(prefix + node.name + (node.isDir ? '/' : ''))
    if (node.children.length) {
      paths.push(...flattenTree(node.children, prefix + node.name + '/'))
    }
  }
  return paths
}

function updateNode(nodes, key, updater) {
  return nodes.map((n) =>
    n._key === key ? updater(n) : { ...n, children: updateNode(n.children, key, updater) },
  )
}

function addChild(nodes, parentKey, newNode) {
  return nodes.map((n) =>
    n._key === parentKey
      ? { ...n, children: [...n.children, newNode] }
      : { ...n, children: addChild(n.children, parentKey, newNode) },
  )
}

function deleteNode(nodes, key) {
  return nodes
    .filter((n) => n._key !== key)
    .map((n) => ({ ...n, children: deleteNode(n.children, key) }))
}

function newNode(isDir) {
  return { _key: crypto.randomUUID(), name: isDir ? 'new_folder' : 'new_file', isDir, children: [] }
}

function TreeNode({ node, depth, onRename, onAddChild, onDelete }) {
  return (
    <div>
      <div className="tree-row" style={{ paddingLeft: depth * 16 }}>
        <input
          type="text"
          value={node.name}
          onChange={(e) => onRename(node._key, e.target.value)}
        />
        {node.isDir && (
          <>
            <button type="button" onClick={() => onAddChild(node._key, false)}>
              +File
            </button>
            <button type="button" onClick={() => onAddChild(node._key, true)}>
              +Folder
            </button>
          </>
        )}
        <button type="button" onClick={() => onDelete(node._key)} aria-label="Delete">
          ×
        </button>
      </div>
      {node.children.map((child) => (
        <TreeNode
          key={child._key}
          node={child}
          depth={depth + 1}
          onRename={onRename}
          onAddChild={onAddChild}
          onDelete={onDelete}
        />
      ))}
    </div>
  )
}

function FileTreeEditor({ fileTree, onChange, clipboard, onCopy }) {
  const [tree, setTree] = useState(() => buildTree(fileTree))

  function emit(next) {
    setTree(next)
    onChange(flattenTree(next))
  }

  function handleRename(key, name) {
    emit(updateNode(tree, key, (n) => ({ ...n, name })))
  }

  function handleAddChild(parentKey, isDir) {
    emit(addChild(tree, parentKey, newNode(isDir)))
  }

  function handleDelete(key) {
    emit(deleteNode(tree, key))
  }

  function handleAddRoot(isDir) {
    emit([...tree, newNode(isDir)])
  }

  return (
    <div className="file-tree-editor">
      <div className="tree-toolbar">
        <span>File tree</span>
        <button type="button" onClick={() => onCopy(flattenTree(tree))}>
          Copy
        </button>
        <button type="button" onClick={() => emit(buildTree(clipboard))} disabled={!clipboard}>
          Paste
        </button>
        <button type="button" onClick={() => emit([])}>
          Clear
        </button>
      </div>
      {tree.map((node) => (
        <TreeNode
          key={node._key}
          node={node}
          depth={0}
          onRename={handleRename}
          onAddChild={handleAddChild}
          onDelete={handleDelete}
        />
      ))}
      <div className="tree-row">
        <button type="button" onClick={() => handleAddRoot(false)}>
          + File
        </button>
        <button type="button" onClick={() => handleAddRoot(true)}>
          + Folder
        </button>
      </div>
    </div>
  )
}

export default FileTreeEditor

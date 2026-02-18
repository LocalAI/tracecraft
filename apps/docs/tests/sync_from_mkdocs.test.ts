/**
 * Tests for the MkDocs to Nextra sync script.
 *
 * These tests verify that the Python sync script correctly converts
 * MkDocs Material markdown syntax to Nextra MDX format.
 */

import { describe, it, expect } from 'vitest'
import { execFileSync } from 'child_process'
import { mkdtempSync, writeFileSync, readFileSync, rmSync, mkdirSync, existsSync } from 'fs'
import { join } from 'path'
import { tmpdir } from 'os'

// Helper to run conversion on a string using execFileSync (safer than exec)
function convertContent(content: string): string {
  const scriptPath = join(__dirname, '..', 'scripts', 'sync_from_mkdocs.py')

  // Create temp directories
  const tempDir = mkdtempSync(join(tmpdir(), 'sync-test-'))
  const docsDir = join(tempDir, 'docs')
  const pagesDir = join(tempDir, 'pages')
  mkdirSync(docsDir)
  mkdirSync(pagesDir)

  // Write test content
  const testFile = join(docsDir, 'test.md')
  writeFileSync(testFile, content)

  try {
    // Run sync using execFileSync with explicit arguments (no shell injection risk)
    execFileSync('python3', [
      scriptPath,
      '--docs-root', docsDir,
      '--pages-root', pagesDir,
    ], {
      encoding: 'utf-8',
      cwd: join(__dirname, '..'),
    })

    // Read result
    const resultFile = join(pagesDir, 'test.mdx')
    if (existsSync(resultFile)) {
      return readFileSync(resultFile, 'utf-8')
    }
    throw new Error('Output file not created')
  } finally {
    // Cleanup
    rmSync(tempDir, { recursive: true, force: true })
  }
}

describe('MkDocs to Nextra Sync Script', () => {
  describe('Admonition Conversion', () => {
    it('converts !!! note to <Callout type="info">', () => {
      const input = `# Test

!!! note
    This is a note.
    It has multiple lines.

More content.`

      const output = convertContent(input)

      expect(output).toContain("import { Callout } from 'nextra/components'")
      expect(output).toContain('<Callout type="info">')
      expect(output).toContain('This is a note.')
      expect(output).toContain('It has multiple lines.')
      expect(output).toContain('</Callout>')
    })

    it('converts !!! warning to <Callout type="warning">', () => {
      const input = `!!! warning "Be Careful"
    This is a warning message.`

      const output = convertContent(input)

      expect(output).toContain('<Callout type="warning">')
      expect(output).toContain('**Be Careful**')
      expect(output).toContain('This is a warning message.')
    })

    it('converts !!! danger to <Callout type="error">', () => {
      const input = `!!! danger
    Critical error information.`

      const output = convertContent(input)

      expect(output).toContain('<Callout type="error">')
    })

    it('converts !!! tip to <Callout type="info">', () => {
      const input = `!!! tip "Pro Tip"
    Here is a helpful tip.`

      const output = convertContent(input)

      expect(output).toContain('<Callout type="info">')
      expect(output).toContain('**Pro Tip**')
    })
  })

  describe('Collapsible Admonition Conversion', () => {
    it('converts ??? question to <Details>', () => {
      const input = `??? question "What is TraceCraft?"
    TraceCraft is an observability SDK.
    It supports multiple backends.`

      const output = convertContent(input)

      expect(output).toContain("import { Details } from '@/components'")
      expect(output).toContain('<Details summary="What is TraceCraft?">')
      expect(output).toContain('TraceCraft is an observability SDK.')
      expect(output).toContain('</Details>')
    })

    it('converts ???+ (open by default) to <Details open>', () => {
      const input = `???+ note "Expanded by default"
    This should be open.`

      const output = convertContent(input)

      expect(output).toContain('<Details summary="Expanded by default" open>')
    })
  })

  describe('Tab Conversion', () => {
    it('converts === tabs to <Tabs>', () => {
      const input = `=== "Python"
    \`\`\`python
    print("Hello")
    \`\`\`

=== "JavaScript"
    \`\`\`javascript
    console.log("Hello")
    \`\`\``

      const output = convertContent(input)

      expect(output).toContain("import { Tabs } from 'nextra/components'")
      expect(output).toContain("<Tabs items={['Python', 'JavaScript']}>")
      expect(output).toContain('<Tabs.Tab>')
      expect(output).toContain('print("Hello")')
      expect(output).toContain('console.log("Hello")')
    })
  })

  describe('Code Block Title Conversion', () => {
    it('converts code block titles to comments', () => {
      const input = `\`\`\`python title="example.py"
def hello():
    print("Hello")
\`\`\``

      const output = convertContent(input)

      expect(output).toContain('{/* example.py */}')
      expect(output).toContain('```python')
      expect(output).not.toContain('title="example.py"')
    })
  })

  describe('Link Conversion', () => {
    it('removes .md extension from links', () => {
      const input = `[Link text](getting-started/quickstart.md)`

      const output = convertContent(input)

      expect(output).toContain('[Link text](/getting-started/quickstart)')
      expect(output).not.toContain('.md)')
    })

    it('converts relative links with ../', () => {
      const input = `[Parent link](../integrations/langchain.md)`

      const output = convertContent(input)

      expect(output).toContain('[Parent link](/integrations/langchain)')
    })
  })

  describe('Import Generation', () => {
    it('combines multiple Nextra imports', () => {
      const input = `!!! note
    A note.

=== "Tab 1"
    Content 1`

      const output = convertContent(input)

      // Both Callout and Tabs should be imported from nextra/components
      expect(output).toContain("import { Callout, Tabs } from 'nextra/components'")
    })

    it('separates Nextra and custom component imports', () => {
      const input = `??? question "FAQ"
    Answer here.

!!! note
    A note.`

      const output = convertContent(input)

      expect(output).toContain("import { Callout } from 'nextra/components'")
      expect(output).toContain("import { Details } from '@/components'")
    })
  })

  describe('Complex Document Conversion', () => {
    it('handles a complete FAQ document', () => {
      const input = `# FAQ

Find answers below.

## Getting Started

??? question "What is TraceCraft?"
    TraceCraft is a vendor-neutral observability SDK.

    \`\`\`python
    import tracecraft
    tracecraft.init()
    \`\`\`

??? question "How do I install it?"
    Use pip:

    \`\`\`bash
    pip install tracecraft
    \`\`\`

!!! tip "Pro Tip"
    Start with console output for local development.`

      const output = convertContent(input)

      // Should have proper structure
      expect(output).toContain('# FAQ')
      expect(output).toContain('## Getting Started')

      // Should have imports
      expect(output).toContain("import { Callout } from 'nextra/components'")
      expect(output).toContain("import { Details } from '@/components'")

      // Should have converted components
      expect(output).toContain('<Details summary="What is TraceCraft?">')
      expect(output).toContain('<Details summary="How do I install it?">')
      expect(output).toContain('<Callout type="info">')
      expect(output).toContain('**Pro Tip**')
    })
  })
})

describe('_meta.ts Generation', () => {
  it('creates _meta.ts with correct entries', () => {
    const tempDir = mkdtempSync(join(tmpdir(), 'sync-test-meta-'))
    const docsDir = join(tempDir, 'docs', 'user-guide')
    const pagesDir = join(tempDir, 'pages', 'user-guide')
    mkdirSync(docsDir, { recursive: true })
    mkdirSync(pagesDir, { recursive: true })

    // Create test files
    writeFileSync(join(docsDir, 'index.md'), '# Overview')
    writeFileSync(join(docsDir, 'configuration.md'), '# Configuration')
    writeFileSync(join(docsDir, 'performance.md'), '# Performance')

    const scriptPath = join(__dirname, '..', 'scripts', 'sync_from_mkdocs.py')

    try {
      // Use execFileSync with explicit arguments (no shell injection risk)
      execFileSync('python3', [
        scriptPath,
        '--docs-root', join(tempDir, 'docs'),
        '--pages-root', join(tempDir, 'pages'),
      ], {
        encoding: 'utf-8',
        cwd: join(__dirname, '..'),
      })

      const metaPath = join(pagesDir, '_meta.ts')
      expect(existsSync(metaPath)).toBe(true)

      const metaContent = readFileSync(metaPath, 'utf-8')
      expect(metaContent).toContain("index: 'Overview'")
      expect(metaContent).toContain("configuration: 'Configuration'")
      expect(metaContent).toContain("performance: 'Performance'")
    } finally {
      rmSync(tempDir, { recursive: true, force: true })
    }
  })
})

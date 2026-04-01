import { saveAs } from 'file-saver'
import jsPDF from 'jspdf'
import { Document, Packer, Paragraph, TextRun, HeadingLevel } from 'docx'
import type { DownloadFormat } from '../types'

function sanitize(name: string) {
  return name.replace(/[\\/:*?"<>|]/g, '-').replace(/-+/g, '-').trim()
}

function extractImage(line: string) {
  const match = line.match(/!\[(.*?)\]\((.*?)\)/)
  if (match) {
    return { alt: match[1].trim(), url: match[2].trim() }
  }
  return null
}

export async function downloadBlog(
  content: string,
  title: string,
  format: DownloadFormat
) {
  const filename = sanitize(title || 'blog')

  if (format === 'markdown') {
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
    saveAs(blob, `${filename}.md`)
    return
  }

  if (format === 'pdf') {
    const doc = new jsPDF({ unit: 'pt', format: 'a4' })
    const margin = 50
    const pageW = doc.internal.pageSize.getWidth()
    const maxW = pageW - margin * 2
    const lines = content.split('\n')
    let y = margin

    for (const line of lines) {
      const imgInfo = extractImage(line)
      if (imgInfo) {
        doc.setFontSize(11).setFont('helvetica', 'italic')
        doc.text(`[Image: ${imgInfo.alt}]`, margin, y)
        y += 20
        continue
      }

      if (y > doc.internal.pageSize.getHeight() - margin) {
        doc.addPage()
        y = margin
      }
      if (line.startsWith('# ')) {
        doc.setFontSize(22).setFont('helvetica', 'bold')
        doc.text(line.slice(2), margin, y)
        y += 30
      } else if (line.startsWith('## ')) {
        doc.setFontSize(16).setFont('helvetica', 'bold')
        doc.text(line.slice(3), margin, y)
        y += 22
      } else if (line.startsWith('### ')) {
        doc.setFontSize(13).setFont('helvetica', 'bold')
        doc.text(line.slice(4), margin, y)
        y += 18
      } else if (line.trim() === '') {
        y += 10
      } else {
        doc.setFontSize(11).setFont('helvetica', 'normal')
        const wrapped = doc.splitTextToSize(line, maxW)
        doc.text(wrapped, margin, y)
        y += wrapped.length * 14
      }
    }
    doc.save(`${filename}.pdf`)
    return
  }

  if (format === 'docx') {
    const lines = content.split('\n')
    const children: Paragraph[] = []

    for (const line of lines) {
      const imgInfo = extractImage(line)
      if (imgInfo) {
        children.push(new Paragraph({
          children: [new TextRun({ text: `[Image: ${imgInfo.alt}]`, italics: true, size: 24 })],
        }))
        continue
      }

      if (line.startsWith('# ')) {
        children.push(new Paragraph({
          text: line.slice(2),
          heading: HeadingLevel.HEADING_1,
        }))
      } else if (line.startsWith('## ')) {
        children.push(new Paragraph({
          text: line.slice(3),
          heading: HeadingLevel.HEADING_2,
        }))
      } else if (line.startsWith('### ')) {
        children.push(new Paragraph({
          text: line.slice(4),
          heading: HeadingLevel.HEADING_3,
        }))
      } else if (line.trim() === '') {
        children.push(new Paragraph({ text: '' }))
      } else {
        children.push(new Paragraph({
          children: [new TextRun({ text: line, size: 24 })],
        }))
      }
    }

    const doc = new Document({
      sections: [{ children }],
    })
    const blob = await Packer.toBlob(doc)
    saveAs(blob, `${filename}.docx`)
  }
}


import JSZip from 'jszip';
import { saveAs } from 'file-saver';
import axios from 'axios';

/**
 * Fetch and download exams as a ZIP archive.
 * @param {Object} params
 * @param {string} params.subjectCode - The subject code (if searching by code).
 * @param {string} params.subjectName - The subject name (if searching by name).
 * @param {function} params.onProgress - Callback for progress updates.
 */
export async function downloadExams({ subjectCode, subjectName, onProgress }) {
  try {
    onProgress({ status: 'Connecting to server...', progress: 0 });

    let url = '';
    let formData = new URLSearchParams();

    if (subjectCode) {
      url = '/api/view1.php';
      formData.append('ccode', subjectCode);
      formData.append('submit', ''); // Sometimes required by PHP forms
    } else if (subjectName) {
      url = '/api/view2.php';
      formData.append('cname', subjectName);
      formData.append('submit', '');
    } else {
      throw new Error('Please provide either a subject code or name.');
    }

    // Fetch the HTML page with the table
    const response = await axios.post(url, formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });

    const htmlString = response.data;
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlString, 'text/html');

    // Find the table rows inside #body > table
    const tableRows = doc.querySelectorAll('#body table tbody tr');
    
    if (!tableRows || tableRows.length < 3) {
      throw new Error('No exams found for the given subject.');
    }

    // The first two rows are usually headers in this specific table structure
    const examRows = Array.from(tableRows).slice(2);
    const totalExams = examRows.length;

    onProgress({ status: `Found ${totalExams} exam(s). Starting download...`, progress: 10 });

    const zip = new JSZip();

    for (let i = 0; i < totalExams; i++) {
      const row = examRows[i];
      const cells = row.querySelectorAll('td');

      if (cells.length < 6) continue;

      const year = cells[2].textContent.trim();
      const semesterCode = cells[3].textContent.trim();
      let subfolder = cells[4].textContent.trim();
      const downloadLinkElement = cells[5].querySelector('a');

      if (!downloadLinkElement || !downloadLinkElement.getAttribute('href')) {
        continue;
      }

      let href = downloadLinkElement.getAttribute('href');
      // Fix relative URLs
      if (!href.startsWith('http')) {
        href = `/api/${href.replace(/^\/+/, '')}`;
      } else {
        href = href.replace('https://cl.thapar.edu/', '/api/');
        href = href.replace('http://cl.thapar.edu/', '/api/');
      }

      // Format subfolder
      if (subfolder.toUpperCase() === 'AUX') {
        subfolder = 'Auxiliary';
      }

      // Format filename
      let newName = `Exam ${year}`;
      if (semesterCode === 'E') {
        newName = `Even Sem ${year}.pdf`;
      } else if (semesterCode === 'O') {
        newName = `Odd Sem ${year}.pdf`;
      } else {
        newName = `${semesterCode} Sem ${year}.pdf`;
      }

      onProgress({ 
        status: `Downloading ${newName} (${i + 1}/${totalExams})...`, 
        progress: 10 + Math.floor(((i) / totalExams) * 80) // 10% to 90%
      });

      // Fetch the actual PDF
      try {
        const pdfResponse = await axios.get(href, { responseType: 'blob' });
        const pdfBlob = pdfResponse.data;

        // Add to JSZip
        zip.folder(subfolder).file(newName, pdfBlob);
      } catch (err) {
        console.error(`Failed to download ${newName}:`, err);
        // Continue downloading others even if one fails
      }
    }

    onProgress({ status: 'Zipping files...', progress: 95 });
    const zipBlob = await zip.generateAsync({ type: 'blob' });

    onProgress({ status: 'Saving...', progress: 100 });
    const zipFilename = `${subjectCode || subjectName || 'Exams'}.zip`;
    saveAs(zipBlob, zipFilename);

    onProgress({ status: 'Download Complete!', progress: 100, done: true });

  } catch (error) {
    console.error('Download Error:', error);
    throw new Error(error.message || 'An error occurred while downloading.');
  }
}

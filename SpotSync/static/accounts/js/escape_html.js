// Escape text before inserting it into an HTML text or quoted-attribute context.
function spotSyncEscapeHtml(value) {
    const entities = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'};
    return String(value).replace(/[&<>"']/g, character => entities[character]);
}

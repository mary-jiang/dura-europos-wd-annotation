function addEditButtons() {
    document.querySelectorAll('.depicted-without-region').forEach(addEditButton);
}

function addEditButton(element) {
    const item = element.closest('.item'),
          subjectId = item.dataset.entityId,
          depictedId = element.firstChild.dataset.entityId,
          image = item.querySelector('.image');
    const button = document.createElement('button');
    button.type = 'button';
    button.classList.add('btn', 'btn-secondary', 'btn-sm');
    button.textContent = 'add region';
    button.addEventListener('click', onClick)
    element.append(document.createTextNode(' '));
    element.append(button);

    let cropper = null;

    function onClick() {
        if (cropper === null) {
            button.textContent = 'loading...';
            image.classList.add('active');
            cropper = new Cropper(image.firstElementChild, {
                viewMode: 2,
                movable: false,
                rotatable: false,
                scalable: false,
                zoomable: false,
                ready: function() {
                    button.textContent = 'use this region';
                },
            });
            document.addEventListener('keydown', onKeyDown);
        } else {
            if (button.textContent === 'loading...') {
                return;
            }
            image.classList.remove('active');
            const cropData = cropper.getData(),
                  imageData = cropper.getImageData(),
                  x = 100 * cropData.x / imageData.naturalWidth,
                  y = 100 * cropData.y / imageData.naturalHeight,
                  w = 100 * cropData.width / imageData.naturalWidth,
                  h = 100 * cropData.height / imageData.naturalHeight,
                  depicted = document.createElement('div');
            depicted.classList.add('depicted')
            depicted.append(element.firstChild.cloneNode(true));
            // note: the browser rounds the percentages a bit,
            // and we’ll use the rounded values for the IIIF region
            depicted.style.left = `${x}%`;
            depicted.style.top = `${y}%`;
            depicted.style.width = `${w}%`;
            depicted.style.height = `${h}%`;
            cropper.destroy();
            cropper = null;
            image.append(depicted);
            function pct(name) {
                return depicted.style[name].replace('%', '');
            }
            const iiifRegion = `pct:${pct('left')},${pct('top')},${pct('width')},${pct('height')}`,
                  quickStatements = `${subjectId}\tP180\t${depictedId}\tP2677\t"${iiifRegion}"`;

            const csrfTokenElement = document.getElementById('csrf_token');
            if (csrfTokenElement !== null) {
                button.textContent = 'adding qualifier…';
                const baseUrl = document.querySelector('link[rel=index]').href.replace(/\/$/, ''),
                      statementId = element.dataset.statementId,
                      csrfToken = csrfTokenElement.textContent;
                fetch(`${baseUrl}/api/add_qualifier/${statementId}/${iiifRegion}/${csrfToken}`, { method: 'POST', credentials: 'include' }).then(response => {
                    if (response.ok) {
                        element.remove();
                    } else {
                        response.text().then(text => {
                            message = `An error occurred:\n\n${text}\n\n`;
                            // we’re not in an event handler, we can’t write to the clipboard directly
                            message += `Here is the new region in QuickStatements syntax:\n\n${quickStatements}`;
                            window.alert(message);
                            element.remove();
                        });
                    }
                });
            } else {
                const loginElement = document.getElementById('login');
                let message = '';
                if (loginElement !== null) {
                    message = 'You are not logged in. ';
                }
                message += 'Copy the new region to the clipboard (in QuickStatements syntax)?';
                if (window.confirm(message)) {
                    navigator.clipboard.writeText(quickStatements);
                    element.remove();
                } else {
                    depicted.remove();
                    button.textContent = 'add region';
                }
            }
        }
        function onKeyDown(eKey) {
            if (eKey.key === 'Escape') {
                cropper.destroy();
                cropper = null;
                image.classList.remove('active');
                document.removeEventListener('keydown', onKeyDown);
                button.textContent = 'add region';
            }
        }
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addEditButtons);
} else {
    addEditButtons();
}

import { addCommentLabel, initializeRegionCommentList, labelLocalQualifierStatement } from "./shared.js";

function setup() {
    const baseUrl = document.querySelector('link[rel=index]').href.replace(/\/$/, '');
    
    function addCommentButtons() {
        // adds comment button for each statement (without qualifiers)
        document.querySelectorAll('.wd-image-positions--depicted-without-region').forEach(addCommentButton);
    }

    function addCommentLabels() {
        // get base level information
        const username = window.location.href.substring(window.location.href.lastIndexOf("/") + 1),
        formData = new FormData();
        const entityDiv = document.querySelector(".wd-image-positions--entity");
        const itemId = entityDiv.getAttribute('data-entity-id');
        formData.append('item_id', itemId);
        formData.append('username', username);
    
        // fetch comments
        return fetch(`${baseUrl}/api/v2/get_comments`, {
            method: 'POST',
            body: formData,
            credentials: 'include',
        }).then(response => {
            if (response.ok) {
                return response.json().then(json => {
                    json.forEach(item => addCommentLabel(item.statement_id, item.project_lead_username, item.comment))
                });
            } else {
                return response.text().then(error => {
                    window.alert(`An error occurred:\n\n${error}`);
                });
            }
        });
    
    }

    function addCommentButton(element) {
        const button = document.createElement('button');
        const span = document.createElement('span');
        span.classList.add('input-span', `comment-input-${element.dataset.statementId}`)
        span.setAttribute('id', `span-${element.dataset.statementId}`)
        span.setAttribute('contenteditable', 'true')
        element.append(span);

        button.type = 'button';
        button.classList.add('btn', 'btn-secondary', 'btn-sm', 'ms-2', `comment-input-${element.dataset.statementId}`);
        button.textContent = 'comment on statement';
        button.addEventListener('click', onClick);
        element.append(button);

        function onClick() {
            const statementId = element.dataset.statementId,
                  username = window.location.href.substring(window.location.href.lastIndexOf("/") + 1),
                  comment = document.getElementById(`span-${element.dataset.statementId}`).innerHTML,
                  formData = new FormData();
            
            if (!comment) {
                alert("Empty comments are not allowed. Please type something into the comment box and try again.");
                return;
            }
            const entityDiv = document.querySelector(".wd-image-positions--entity");
            const itemId = entityDiv.getAttribute('data-entity-id')

            formData.append('statement_id', statementId);
            formData.append('comment', comment);
            formData.append('item_id', itemId);
            formData.append('username', username)

            return fetch(`${baseUrl}/api/v2/add_comment`, {
                method: 'POST',
                body: formData,
                credentials: 'include',
            }).then(response => {
                if (response.ok) {
                    document.getElementById(`span-${element.dataset.statementId}`).innerHTML = ""
                    return response.json().then(json => {
                        const comment = json.comment;
                        const projectLeadUsername = json.project_lead_username;
                        const statementId = json.statement_id;
                        addCommentLabel(statementId, projectLeadUsername, comment)
                    });
                } else {
                    return response.text().then(error => {
                        window.alert(`An error occurred:\n\n${error}`);
                    });
                }
            });
        }
    }
    
    function addCommentOnRegionButton(entityElement) {
        const button = document.createElement('button');
        button.type = 'button';
        button.classList.add('btn', 'btn-secondary');
        button.textContent = 'Comment on a region';
        button.addEventListener('click', addCommentRegionListeners);
        const buttonWrapper = document.createElement('div');
        buttonWrapper.append(button);
        addUploadButton(buttonWrapper);
        entityElement.append(buttonWrapper);

        let onKeyDown = null;
        let cancelButton = null;
        cancelButton = document.createElement('button');
        cancelButton.type = 'button';
        cancelButton.classList.add('btn', 'btn-secondary', 'btn-sm', 'wd-image-positions--active', 'ms-2');
        cancelButton.textContent = 'cancel';

        function addCommentRegionListeners() {
            button.textContent = "Select a region on comment on";
            button.classList.add('wd-image-positions--active')
            for (const depicted of entityElement.querySelectorAll('.wd-image-positions--depicted')) {
                depicted.addEventListener('click', commentRegion);
            }
            button.removeEventListener('click', addCommentRegionListeners);

            cancelButton.addEventListener('click', cancelCommentRegion);
            buttonWrapper.append(cancelButton)
        }

        function commentRegion(event) {
            event.preventDefault();
            for (const depicted of entityElement.querySelectorAll('.wd-image-positions--depicted')) {
                depicted.removeEventListener('click', commentRegion);
            }
            const depicted = event.target.closest('.wd-image-positions--depicted');
            const statementId = depicted.getAttribute("data-statement-id"),
                  title = depicted.getAttribute("title"),
                  formData = new FormData();
            formData.append('statement_id', statementId)


            const entityDiv = document.querySelector(".wd-image-positions--entity");
            const itemId = entityDiv.getAttribute('data-entity-id');
            const username = window.location.href.substring(window.location.href.lastIndexOf("/") + 1);
            formData.append('item_id', itemId);
            formData.append('username', username);

            const statementsList = document.querySelector(".wd-image-positions--depicteds-without-region")

            const label = document.createElement('h4');
            label.innerHTML = `Commenting on region with label: ${title}`;
            label.classList.add('region-comment-input');
            const span = document.createElement('span');
            span.classList.add('input-span', 'region-comment-input');
            span.setAttribute('id', 'region-comment-input-span');
            span.setAttribute('contenteditable', 'true');
            const submitButton = document.createElement('button');
            submitButton.type = 'button';
            submitButton.classList.add('btn', 'btn-secondary','btn-sm', 'ms-2', 'region-comment-input');
            submitButton.textContent = 'Submit Comment';
            submitButton.addEventListener('click', onClick);
            const brk = document.createElement('br');

            function onClick() {
                const comment = document.querySelector('#region-comment-input-span').innerHTML;
                formData.append('comment', comment);

                return fetch(`${baseUrl}/api/v2/add_comment`, {
                    method: 'POST',
                    body: formData,
                    credentials: 'include',
                }).then(response => {
                    if (response.ok) {
                        document.querySelector('#region-comment-input-span').innerHTML = ""
                        return response.json().then(json => {
                            const comment = json.comment;
                            const projectLeadUsername = json.project_lead_username;
                            const statementId = json.statement_id;
                            addCommentLabel(statementId, projectLeadUsername, comment)
                            document.querySelectorAll(".region-comment-input").forEach(e => e.remove());
                        });
                    } else {
                        return response.text().then(error => {
                            window.alert(`An error occurred:\n\n${error}`);
                        });
                    }
                });
            }

            statementsList.prepend(brk)
            statementsList.prepend(submitButton)
            statementsList.prepend(span);
            statementsList.prepend(label)

            cancelCommentRegion();
        }

        function cancelCommentRegion() {
            for (const depicted of entityElement.querySelectorAll('.wd-image-positions--depicted')) {
                depicted.removeEventListener('click', commentRegion);
            }
            button.textContent = 'Comment on a region';
            button.addEventListener('click', addCommentRegionListeners);
            document.removeEventListener('keydown', onKeyDown);
            cancelButton.remove();
        }

    }

    function addUploadButton(element) {
        const button = document.createElement('button');
        button.type = 'button';
        button.classList.add('btn', 'btn-secondary');
        button.textContent = 'Approve and upload annotations';
        button.addEventListener('click', onClick);
        element.append(button);

        const formData = new FormData();
        const entityDiv = document.querySelector(".wd-image-positions--entity");
        const itemId = entityDiv.getAttribute('data-entity-id'),
              username = window.location.href.substring(window.location.href.lastIndexOf("/") + 1);
        formData.append('item_id', itemId);
        formData.append('username', username)

        function onClick() {
            return fetch(`${baseUrl}/api/v2/upload_annotations`, {
                method: 'POST',
                body: formData,
                credentials: 'include',
            }).then(response => {
                if (response.ok) {
                    document.querySelectorAll(".wd-image-positions--depicteds-without-region__P180").forEach(e => e.remove());
                    document.querySelectorAll(".wd-image-positions--depicted__P180").forEach(e => e.remove());
                    alert("Uploaded to Wikidata!");
                    return;
                } else {
                    return response.text().then(error => {
                        window.alert(`An error occurred:\n\n${error}`);
                    });
                }
            });

           
        }
       
    }

    addCommentButtons();
    initializeRegionCommentList();
    addCommentLabels();
    document.querySelectorAll('.wd-image-positions--depicted').forEach(div => {
        labelLocalQualifierStatement(div);
    });
    document.querySelectorAll('.wd-image-positions--entity').forEach(entityElement => {
        addCommentOnRegionButton(entityElement);
    });

}

setup();
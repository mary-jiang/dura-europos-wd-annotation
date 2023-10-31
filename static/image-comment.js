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
                    console.log(json)
                    json.forEach(item => addCommentLabel(item.statement_id, item.project_lead_username, item.comment))
                });
            } else {
                return response.text().then(error => {
                    window.alert(`An error occurred:\n\n${error}`);
                });
            }
        });

    }

    function addCommentLabel(statementId, projectLeadUsername, comment) {
        let commentList = document.querySelector(`#comment-list-${statementId}`);
        if (!commentList) {
            commentList = document.createElement('ul');
            commentList.setAttribute('id', `comment-list-${statementId}`)
            const parent = document.querySelector(`[data-statement-id="${statementId}"]`);
            parent.appendChild(commentList);
        }
        let comment_item = document.createElement('li');
        let comment_text = document.createTextNode(`${projectLeadUsername}: ${comment}`);
        comment_item.appendChild(comment_text);

        commentList.append(comment_item);
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
                    // TODO: append the statement into here
                    document.getElementById(`span-${element.dataset.statementId}`).innerHTML = ""
                    // TODO: return the statement id too, use that to grab the whatever and add the comment below that
                    return response.json().then(json => {
                        const comment = json.comment;
                        const projectLeadUsername = json.project_lead_username;
                        const statementId = json.statement_id;
                        // console.log(comment, projectLeadUsername)
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

    addCommentButtons();
    addCommentLabels();
    // TODO: load comments into here somehow
}

setup()
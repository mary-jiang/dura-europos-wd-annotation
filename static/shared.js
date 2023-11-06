export function addCommentLabel(statementId, projectLeadUsername, comment) {
    let commentList = document.querySelector(`#comment-list-${statementId}`);
    if (!commentList) {
        commentList = document.createElement('ul');
        commentList.setAttribute('id', `comment-list-${statementId}`)
        const parent = document.querySelector(`[data-statement-id="${statementId}"]`);
        if (parent.classList.contains('wd-image-positions--depicted-without-region')) {
            parent.appendChild(commentList);
        } else {
            let title = parent.children[0].text
            let regionParent = document.querySelector(`#region-comment-list-${statementId}`);
            if (!regionParent) {
                regionParent = document.createElement('ul');
                let mainBulletPoint = document.createElement('li');
                let mainBulletPointText = document.createTextNode(title);
                mainBulletPoint.appendChild(mainBulletPointText);
                regionParent.appendChild(mainBulletPoint);
                mainBulletPoint.append(commentList);
                regionParent.setAttribute('id', `region-comment-list-${statementId}`);
                document.querySelector('#region-comment-list-div').append(regionParent);
            }

        }
    }
    let commentItem = document.createElement('li');
    let commentText = document.createTextNode(`${projectLeadUsername}: ${comment}`);
    commentItem.appendChild(commentText);

    commentList.append(commentItem);
}

export function initializeRegionCommentList() {
    const wrapper = document.querySelector('.wd-image-positions--entity');

    let regionCommentList = document.createElement('div');
    let label = document.createElement('p');
    label.innerHTML = "Comments on statements with regions: "
    regionCommentList.appendChild(label)
    regionCommentList.setAttribute('id', 'region-comment-list-div')
    wrapper.append(regionCommentList);
    
}

export function labelLocalQualifierStatement(div) {
    let child = div.children[0];
    let oldText = child.text;
    const statementId = div.getAttribute("data-statement-id");

    if (!statementId.includes("Q")) {
        child.text = statementId + ": " + oldText;
    }
}
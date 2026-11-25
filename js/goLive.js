// 初始化WebSocket连接
        const socket = io('http://localhost:5001');
        
        // DOM元素
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');
        const emergencyStopBtn = document.getElementById('emergency-stop-btn');
        const userGoalInput = document.getElementById('user-goal');
        const statusText = document.getElementById('status-text');
        const statusLight = document.getElementById('status-light');
        const screenshotImg = document.getElementById('screenshot-img');
        const historyList = document.getElementById('history-list');
        const confirmationDialog = document.getElementById('confirmation-dialog');
        const confirmationMessage = document.getElementById('confirmation-message');
        const confirmBtn = document.getElementById('confirm-btn');
        const cancelBtn = document.getElementById('cancel-btn');
        
        // 状态更新处理
        socket.on('status_update', (data) => {
            console.log('Status update:', data);
            
            // 更新状态
            statusText.textContent = data.status;
            statusLight.className = `status-light ${data.status}`;
            
            // 更新截图预览
            if (data.screenshot) {
                screenshotImg.src = `data:image/png;base64,${data.screenshot}`;
            }
            
            // 更新操作历史
            if (data.current_operation) {
                const li = document.createElement('li');
                li.innerHTML = `
                    <strong>${new Date().toLocaleString()}</strong><br>
                    操作: ${data.current_operation.decision.tool_name}<br>
                    结果: ${data.current_operation.execution_result.success ? '成功' : '失败'}<br>
                    信息: ${data.current_operation.execution_result.message}
                `;
                historyList.appendChild(li);
                historyList.scrollTop = historyList.scrollHeight;
            }
            
            // 更新按钮状态
            if (data.status === 'active' || data.status === 'started') {
                startBtn.disabled = true;
                stopBtn.disabled = false;
            } else {
                startBtn.disabled = false;
                stopBtn.disabled = true;
            }
        });
        
        // 操作确认请求处理
        socket.on('action_confirmation_request', (data) => {
            confirmationMessage.textContent = `
                AI建议执行: ${data.decision.tool_name}<br>
                参数: ${JSON.stringify(data.decision.arguments)}<br>
                置信度: ${(data.decision.confidence * 100).toFixed(1)}%<br>
                理由: ${data.decision.explanation}
            `;
            confirmationDialog.style.display = 'block';
        });
        
        // 开始按钮点击事件
        startBtn.addEventListener('click', () => {
            const userGoal = userGoalInput.value.trim();
            if (!userGoal) {
                alert('请输入您的目标');
                return;
            }
            
            // 发送启动请求
            fetch('http://localhost:5001/api/go-live/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ user_goal: userGoal })
            })
            .then(response => response.json())
            .then(data => {
                console.log('Go Live started:', data);
            })
            .catch(error => {
                console.error('Error starting Go Live:', error);
            });
        });
        
        // 停止按钮点击事件
        stopBtn.addEventListener('click', () => {
            fetch('http://localhost:5001/api/go-live/stop', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                console.log('Go Live stopped:', data);
            })
            .catch(error => {
                console.error('Error stopping Go Live:', error);
            });
        });
        
        // 紧急停止按钮点击事件
        emergencyStopBtn.addEventListener('click', () => {
            if (confirm('确定要紧急停止Go Live模式吗？')) {
                fetch('http://localhost:5001/api/go-live/stop', {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    console.log('Emergency stop triggered:', data);
                    alert('Go Live模式已紧急停止');
                })
                .catch(error => {
                    console.error('Error during emergency stop:', error);
                });
            }
        });
        
        // 确认按钮点击事件
        confirmBtn.addEventListener('click', () => {
            // 发送确认信号
            socket.emit('confirm_action', {
                // 确认信息
            });
            confirmationDialog.style.display = 'none';
        });
        
        // 取消按钮点击事件
        cancelBtn.addEventListener('click', () => {
            confirmationDialog.style.display = 'none';
        });
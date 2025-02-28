import JobService from '@baserow/modules/core/services/job'

/**
 * To use this mixin you need to create the following methods on your component:
 * - `getCustomHumanReadableJobState(state)` returns the human readable message your
 *   custom state values.
 * - onJobDone() (optional) is called when the job is finished
 * - onJobFailure() (optional) is called if the job failed
 * - onJobError(error) (optional) is there is an exception during the job polling
 *
 */
export default {
  data() {
    return {
      job: null,
      pollInterval: null,
    }
  },
  computed: {
    jobIsRunning() {
      return (
        this.job !== null && !['failed', 'finished'].includes(this.job.state)
      )
    },
    jobIsFinished() {
      return (
        this.job !== null && ['failed', 'finished'].includes(this.job.state)
      )
    },
    jobHasSucceeded() {
      return this.job?.state === 'finished'
    },
    jobHasFailed() {
      return this.job?.state === 'failed'
    },
    jobHumanReadableState() {
      if (this.job === null) {
        return ''
      }
      const translations = {
        pending: this.$t('job.statePending'),
        started: this.$t('job.stateStarted'),
        failed: this.$t('job.stateFailed'),
        finished: this.$t('job.stateFinished'),
      }
      if (translations[this.job.state]) {
        return translations[this.job.state]
      }
      return this.getCustomHumanReadableJobState(this.job.state)
    },
  },
  methods: {
    /**
     * Call this method to start polling the job progress.
     *
     * @param {object} job the job you want to track.
     */
    startJobPoller(job) {
      this.job = job
      this.pollInterval = setInterval(this.getLatestJobInfo, 1000)
    },
    async getLatestJobInfo() {
      try {
        const { data } = await JobService(this.$client).get(this.job.id)
        this.job = data
        if (this.jobHasFailed) {
          this.stopPollIfRunning()
          if (this.onJobFailure) {
            await this.onJobFailure()
          }
        } else if (!this.jobIsRunning) {
          this.stopPollIfRunning()
          if (this.onJobDone) {
            await this.onJobDone()
          }
        }
      } catch (error) {
        this.stopPollIfRunning()
        if (this.onJobError) {
          this.onJobError(error)
        }
        this.job = null
      }
    },
    stopPollIfRunning() {
      if (this.pollInterval) {
        clearInterval(this.pollInterval)
        this.pollInterval = null
      }
    },
  },
}

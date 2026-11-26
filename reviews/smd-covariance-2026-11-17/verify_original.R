# Baseline: exact retained CRAN source and package data; no package installation.
# Changes are diagnostic sensitivities, not a validated replacement release.
options(digits=14)
# GPL-2.0-or-later: replay using retained GPL package functions.
file_arg <- grep('^--file=', commandArgs(FALSE), value=TRUE)
stopifnot(length(file_arg)==1)
base <- dirname(normalizePath(sub('^--file=', '', file_arg)))
original <- file.path(base,'third_party','metavcov')
out <- file.path(base,'replay-output')
dir.create(out,showWarnings=FALSE)
source(file.path(original,'r.vcov.R'))
source(file.path(original,'smd.vcov.R'))
source(file.path(original,'metafixed.R'))
load(file.path(original,'Geeganage2010.rda'))

dat <- Geeganage2010
cat('Dataset dimensions and fields\n')
print(dim(dat)); print(names(dat))
nt <- as.matrix(dat[,c('nt_SBP','nt_DBP')])
nc <- as.matrix(dat[,c('nc_SBP','nc_DBP')])
d <- as.matrix(dat[,c('SMD_SBP','SMD_DBP')])
stopifnot(all(is.finite(nt)),all(is.finite(nc)),all(is.finite(d)))
rho <- .71
r <- rep(list(matrix(c(1,rho,rho,1),2,2)),nrow(d))
run <- function(f,input_d=d) f(nt=nt,nc=nc,d=input_d,r=r,name=c('SBP','DBP'))
original <- run(smd.vcov)
printed_ef <- matrix(c(-.075002006,-.19339306,.043155405,-.01610660,
  -.242782681,-.31689607,-.097028863,-.16608808,-.004460966,-.13364520,
  -.286780271,.08887979),6,2,byrow=TRUE)
printed_S <- matrix(c(.15560955,.11051462,.15591453,.18256182,.12959901,.18254277,
  .03190808,.02264927,.03198210,.03115906,.02212545,.03119080,
  .01965510,.01395547,.01967717,.26813782,.18910349,.26680797),6,3,byrow=TRUE)
stopifnot(max(abs(as.matrix(original$ef)[1:6,]-printed_ef))<5.1e-9,
          max(abs(original$matrix.vcov[1:6,]-printed_S))<5.1e-9)
cat('\nBaseline matches all first-six published effects and covariance rows at printed precision.\n')
sp <- sqrt(((nt-1)*as.matrix(dat[,c('sdt_SBP','sdt_DBP')])^2+
            (nc-1)*as.matrix(dat[,c('sdc_SBP','sdc_DBP')])^2)/(nt+nc-2))
raw_d_reconstructed <- as.matrix(dat[,c('MD_SBP','MD_DBP')])/sp
cat('\nMaximum difference between provided SMD and MD/pooledSD: ')
print(max(abs(d-raw_d_reconstructed)))
write.csv(data.frame(studyID=dat$studyID,provided_SBP=d[,1],provided_DBP=d[,2],
  reconstructed_raw_SBP=raw_d_reconstructed[,1],reconstructed_raw_DBP=raw_d_reconstructed[,2]),
  file.path(out,'published_example_input_check.csv'),row.names=FALSE)

# Make controlled copies by replacing exactly one matching assignment each.
replace_assignment <- function(fun,lhs,new_rhs) {
  count <- 0L
  walk <- function(x) {
    if (!is.call(x)) return(x)
    if (identical(x[[1]],as.name('<-')) && identical(x[[2]],lhs)) {
      count <<- count+1L
      return(as.call(list(as.name('<-'),lhs,new_rhs)))
    }
    for (ii in seq_along(x)[-1]) x[ii] <- list(walk(x[[ii]]))
    x
  }
  body(fun) <- walk(body(fun))
  stopifnot(count==1L)
  fun
}
q_overlap <- function(n1,n2,m) m-m/n1-m/n2+m*m/(n1*n2)
new_k <- quote(2*(q_overlap(nt[k,i],nt[k,j],n_rt[[k]][i,j])+
                    q_overlap(nc[k,i],nc[k,j],n_rc[[k]][i,j]))/(vi*vj))
k_fun <- replace_assignment(smd.vcov,quote(kij),new_k)
j_fun <- replace_assignment(smd.vcov,quote(g[k,i]),quote(d[k,i]*jvi))
both_fun <- replace_assignment(k_fun,quote(g[k,i]),quote(d[k,i]*jvi))
variants <- list(original=original,J_only_covariance_held_fixed=run(j_fun),
                 k_only_effects_held_fixed=run(k_fun),J_and_k=run(both_fun),
                 raw_input_only=run(smd.vcov,raw_d_reconstructed),
                 raw_input_J_only=run(j_fun,raw_d_reconstructed),
                 raw_input_J_and_k=run(both_fun,raw_d_reconstructed))
df <- nt+nc-2
J <- 1-3/(4*df-1)
stopifnot(max(abs(as.matrix(variants$original$ef)-d/J))<1e-12,
          max(abs(as.matrix(variants$J_only_covariance_held_fixed$ef)-d*J))<1e-12,
          max(abs(variants$J_only_covariance_held_fixed$matrix.vcov-original$matrix.vcov))<1e-12,
          max(abs(as.matrix(variants$k_only_effects_held_fixed$ef)-as.matrix(original$ef)))<1e-12)

# Independent GLS using direct normal equations cross-checks unchanged metafixed.
own_gls <- function(y,S) {
  W <- lapply(S,solve)
  info <- Reduce('+',W)
  rhs <- Reduce('+',lapply(seq_len(nrow(y)),function(i) W[[i]]%*%as.numeric(y[i,])))
  V <- solve(info)
  list(beta=as.numeric(V%*%rhs),V=V)
}
summaries <- list()
for (scenario in names(variants)) {
  obj <- variants[[scenario]]
  stopifnot(all(vapply(obj$list.vcov,function(S)min(eigen(S,symmetric=TRUE)$values)>0,logical(1))))
  fit <- metafixed(y=obj$ef,Slist=obj$list.vcov)
  independent <- own_gls(as.matrix(obj$ef),obj$list.vcov)
  stopifnot(max(abs(fit$coefficients-independent$beta))<1e-10,
            max(abs(fit$vcov-independent$V))<1e-10)
  beta <- as.numeric(fit$coefficients); se <- sqrt(diag(fit$vcov))
  summaries[[scenario]] <- data.frame(scenario=scenario,outcome=c('SBP','DBP'),
     estimate=beta,se=se,lower95=beta-qnorm(.975)*se,upper95=beta+qnorm(.975)*se,
     p=2*pnorm(abs(beta/se),lower.tail=FALSE),Q=fit$Q,df=fit$df)
}
results <- do.call(rbind,summaries)
cat('\nOriginal-source bivariate fixed-effect example and sensitivities\n')
print(results,row.names=FALSE)
write.csv(results,file.path(out,'published_example_results.csv'),row.names=FALSE)

study <- data.frame(ID=dat$studyID,
   nt_SBP=nt[,1],nc_SBP=nc[,1],nt_DBP=nt[,2],nc_DBP=nc[,2],
   input_d_SBP=d[,1],input_d_DBP=d[,2],
   original_g_SBP=as.matrix(original$ef)[,1],original_g_DBP=as.matrix(original$ef)[,2],
   J_corrected_g_SBP=(d*J)[,1],J_corrected_g_DBP=(d*J)[,2],
   original_var_SBP=vapply(original$list.vcov,function(S)S[1,1],numeric(1)),
   original_var_DBP=vapply(original$list.vcov,function(S)S[2,2],numeric(1)),
   original_cov=vapply(original$list.vcov,function(S)S[1,2],numeric(1)),
   k_corrected_var_SBP=vapply(variants$J_and_k$list.vcov,function(S)S[1,1],numeric(1)),
   k_corrected_var_DBP=vapply(variants$J_and_k$list.vcov,function(S)S[2,2],numeric(1)),
   k_corrected_cov=vapply(variants$J_and_k$list.vcov,function(S)S[1,2],numeric(1)))
study$cov_change_percent <- (study$k_corrected_cov/study$original_cov-1)*100
study$var_SBP_change_percent <- (study$k_corrected_var_SBP/study$original_var_SBP-1)*100
study$var_DBP_change_percent <- (study$k_corrected_var_DBP/study$original_var_DBP-1)*100
write.csv(study,file.path(out,'published_example_study_values.csv'),row.names=FALSE)
write.csv(dat,file.path(out,'Geeganage2010_export.csv'),row.names=FALSE)
cat('\nStudy-specific sensitivity ranges in percent\n')
print(sapply(study[,grep('change_percent',names(study))],range))
cat('\nMatched outcome observation counts in all supplied rows: ')
print(all(nt[,1]==nt[,2])&&all(nc[,1]==nc[,2]))
cat('\nAll explicit controls and GLS comparisons passed.\n')
print(sessionInfo())
